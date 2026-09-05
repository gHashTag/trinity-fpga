//! HTTP entrypoint for the GitHub collaboration backend.
//!
//! Routing and transport only; the GitHub logic lives in github_collab.zig so
//! it can be unit-tested without a socket. Run:
//!
//!     tri-github-collab            # PORT from the environment, 8080 default
//!
//! See github_collab.zig for why this is an OAuth App rather than a GitHub App
//! (short version: Zig 0.16 std can verify RSA but not sign it, so there is no
//! RS256 signer available for App JWTs).

const std = @import("std");
const collab = @import("github_collab.zig");

const READ_BUF = 64 * 1024;
/// A spec is a few KB; anything past this is not a spec edit.
const MAX_BODY = 512 * 1024;

pub fn main(init: std.process.Init) !void {
    const gpa = init.gpa;
    const io = init.io;

    const cfg = collab.Config.fromEnv(init.environ_map) catch |err| {
        std.log.err("configuration incomplete: {s}", .{@errorName(err)});
        std.log.err("required: GITHUB_CLIENT_ID GITHUB_CLIENT_SECRET GITHUB_WEBHOOK_SECRET PUBLIC_ORIGIN", .{});
        std.process.exit(1);
    };

    const addr = try std.Io.net.IpAddress.parse("0.0.0.0", cfg.port);
    var listener = try std.Io.net.IpAddress.listen(&addr, io, .{ .reuse_address = true });
    defer listener.close(io);

    std.log.info("github-collab listening on 0.0.0.0:{d}, origin {s}", .{ cfg.port, cfg.public_origin });

    while (true) {
        const conn = listener.accept(io) catch |err| {
            std.log.warn("accept failed: {s}", .{@errorName(err)});
            continue;
        };
        // One connection at a time. This service handles occasional
        // interactive requests, not throughput; a thread pool would be more
        // moving parts than the traffic justifies.
        serve(gpa, io, cfg, conn) catch |err| {
            std.log.warn("connection error: {s}", .{@errorName(err)});
        };
        conn.close(io);
    }
}

fn serve(gpa: std.mem.Allocator, io: std.Io, cfg: collab.Config, conn: std.Io.net.Stream) !void {
    var in_buf: [READ_BUF]u8 = undefined;
    var out_buf: [READ_BUF]u8 = undefined;
    var reader = conn.reader(io, &in_buf);
    var writer = conn.writer(io, &out_buf);

    // `interface` is a field on both, not a method.
    var server = std.http.Server.init(&reader.interface, &writer.interface);
    var request = server.receiveHead() catch return;

    const target = request.head.target;
    const path = if (std.mem.indexOfScalar(u8, target, '?')) |q| target[0..q] else target;

    if (std.mem.eql(u8, path, "/health")) {
        return respondJson(&request, cfg, .ok, "{\"status\":\"ok\",\"service\":\"github-collab\"}");
    }

    if (std.mem.eql(u8, path, "/auth/github")) {
        // `state` is echoed back by GitHub and compared on return; it is what
        // stops a third party from feeding a victim a prepared callback URL.
        var nonce: [16]u8 = undefined;
        // randomSecure, not random: this is a CSRF token, so it must come
        // from the OS CSPRNG rather than a fast non-cryptographic source.
        try std.Io.randomSecure(io, &nonce);
        var hex: [32]u8 = undefined;
        const state = try std.fmt.bufPrint(&hex, "{x}", .{nonce});

        const url = try collab.authorizeUrl(gpa, cfg, state);
        defer gpa.free(url);

        const cookie = try std.fmt.allocPrint(
            gpa,
            "t27_state={s}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=600",
            .{state},
        );
        defer gpa.free(cookie);

        return request.respond("", .{
            .status = .found,
            .extra_headers = &.{
                .{ .name = "location", .value = url },
                .{ .name = "set-cookie", .value = cookie },
            },
        });
    }

    if (std.mem.eql(u8, path, "/auth/callback")) {
        const query = if (std.mem.indexOfScalar(u8, target, '?')) |q| target[q + 1 ..] else "";
        const code = findParam(query, "code") orelse
            return respondJson(&request, cfg, .bad_request, "{\"error\":\"missing code\"}");
        const state = findParam(query, "state") orelse
            return respondJson(&request, cfg, .bad_request, "{\"error\":\"missing state\"}");

        // Compare against the cookie set at /auth/github. Without this the
        // callback accepts any code anyone can produce.
        const cookie_state = headerValue(&request, "cookie") orelse "";
        if (!cookieHas(cookie_state, "t27_state", state)) {
            return respondJson(&request, cfg, .bad_request, "{\"error\":\"state mismatch\"}");
        }

        const tok = collab.exchangeCode(gpa, io, cfg, code) catch |err| {
            std.log.warn("token exchange failed: {s}", .{@errorName(err)});
            return respondJson(&request, cfg, .bad_gateway, "{\"error\":\"token exchange failed\"}");
        };
        defer gpa.free(tok.access_token);
        defer gpa.free(tok.scope);

        // The token goes to the browser in a cookie, never into the redirect
        // URL: query strings land in history, logs and Referer headers.
        const cookie = try std.fmt.allocPrint(
            gpa,
            "t27_gh={s}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=28800",
            .{tok.access_token},
        );
        defer gpa.free(cookie);

        const back = try std.fmt.allocPrint(gpa, "{s}/#/specs?connected=1", .{cfg.allowed_origin});
        defer gpa.free(back);

        return request.respond("", .{
            .status = .found,
            .extra_headers = &.{
                .{ .name = "location", .value = back },
                .{ .name = "set-cookie", .value = cookie },
            },
        });
    }

    if (std.mem.eql(u8, path, "/webhook")) {
        // Headers first, and copied. `iterateHeaders` asserts the reader is
        // still at `received_head`, so reading the body first turns any later
        // header access into a panic -- and the slices point into the head
        // buffer, which the body read is free to reuse.
        const sig_raw = headerValue(&request, "x-hub-signature-256") orelse
            return respondJson(&request, cfg, .unauthorized, "{\"error\":\"unsigned\"}");
        const sig = try gpa.dupe(u8, sig_raw);
        defer gpa.free(sig);

        const event_raw = headerValue(&request, "x-github-event") orelse "unknown";
        const event = try gpa.dupe(u8, event_raw);
        defer gpa.free(event);

        const body = try readBody(gpa, &request);
        defer gpa.free(body);

        if (!collab.verifySignature(cfg.webhook_secret, body, sig)) {
            std.log.warn("webhook signature rejected", .{});
            return respondJson(&request, cfg, .unauthorized, "{\"error\":\"bad signature\"}");
        }

        std.log.info("webhook accepted: {s} ({d} bytes)", .{ event, body.len });
        return respondJson(&request, cfg, .ok, "{\"ok\":true}");
    }

    if (std.mem.eql(u8, path, "/api/propose")) {
        if (request.head.method == .OPTIONS) return respondJson(&request, cfg, .no_content, "");
        // Same ordering rule as /webhook: header before body, and copied.
        const token_raw = cookieValue(headerValue(&request, "cookie") orelse "", "t27_gh") orelse
            return respondJson(&request, cfg, .unauthorized, "{\"error\":\"not connected\"}");
        const token = try gpa.dupe(u8, token_raw);
        defer gpa.free(token);

        const body = try readBody(gpa, &request);
        defer gpa.free(body);

        const parsed = std.json.parseFromSlice(struct {
            owner: []const u8,
            repo: []const u8,
            path: []const u8,
            content: []const u8,
            title: []const u8,
            body: []const u8,
        }, gpa, body, .{ .ignore_unknown_fields = true }) catch
            return respondJson(&request, cfg, .bad_request, "{\"error\":\"bad json\"}");
        defer parsed.deinit();

        var nonce_bytes: [6]u8 = undefined;
        try std.Io.randomSecure(io, &nonce_bytes);
        const nonce = std.mem.readInt(u48, &nonce_bytes, .little);

        const pr = collab.openPullRequest(gpa, io, token, .{
            .owner = parsed.value.owner,
            .repo = parsed.value.repo,
            .path = parsed.value.path,
            .content = parsed.value.content,
            .title = parsed.value.title,
            .body = parsed.value.body,
        }, nonce) catch |err| {
            std.log.warn("pull request failed: {s}", .{@errorName(err)});
            const msg = switch (err) {
                error.GitHubUnauthorized => "{\"error\":\"no push access to that repository\"}",
                error.GitHubNotFound => "{\"error\":\"repository or path not found\"}",
                error.GitHubUnprocessable => "{\"error\":\"nothing to change, or branch exists\"}",
                else => "{\"error\":\"could not open the pull request\"}",
            };
            return respondJson(&request, cfg, .bad_gateway, msg);
        };
        defer gpa.free(pr.url);

        const out = try std.fmt.allocPrint(
            gpa,
            "{{\"url\":{f},\"number\":{d}}}",
            .{ std.json.fmt(pr.url, .{}), pr.number },
        );
        defer gpa.free(out);
        return respondJson(&request, cfg, .ok, out);
    }

    return respondJson(&request, cfg, .not_found, "{\"error\":\"no such endpoint\"}");
}

fn respondJson(
    request: *std.http.Server.Request,
    cfg: collab.Config,
    status: std.http.Status,
    body: []const u8,
) !void {
    return request.respond(body, .{
        .status = status,
        .extra_headers = &.{
            .{ .name = "content-type", .value = "application/json" },
            // The page lives on another origin, so it needs CORS -- scoped to
            // that one origin, never "*", because these requests carry a
            // credentialed cookie.
            .{ .name = "access-control-allow-origin", .value = cfg.allowed_origin },
            .{ .name = "access-control-allow-credentials", .value = "true" },
            .{ .name = "access-control-allow-headers", .value = "content-type" },
            .{ .name = "vary", .value = "origin" },
        },
    });
}

fn readBody(gpa: std.mem.Allocator, request: *std.http.Server.Request) ![]u8 {
    var transfer: [8 * 1024]u8 = undefined;
    const body_reader = request.readerExpectNone(&transfer);
    return body_reader.allocRemaining(gpa, .limited(MAX_BODY));
}

fn headerValue(request: *std.http.Server.Request, name: []const u8) ?[]const u8 {
    var it = request.iterateHeaders();
    while (it.next()) |h| {
        if (std.ascii.eqlIgnoreCase(h.name, name)) return h.value;
    }
    return null;
}

/// One `key=value` out of a urlencoded query string.
fn findParam(query: []const u8, key: []const u8) ?[]const u8 {
    var it = std.mem.splitScalar(u8, query, '&');
    while (it.next()) |pair| {
        const eq = std.mem.indexOfScalar(u8, pair, '=') orelse continue;
        if (std.mem.eql(u8, pair[0..eq], key)) return pair[eq + 1 ..];
    }
    return null;
}

fn cookieValue(header: []const u8, key: []const u8) ?[]const u8 {
    var it = std.mem.splitSequence(u8, header, "; ");
    while (it.next()) |pair| {
        const eq = std.mem.indexOfScalar(u8, pair, '=') orelse continue;
        if (std.mem.eql(u8, std.mem.trim(u8, pair[0..eq], " "), key)) return pair[eq + 1 ..];
    }
    return null;
}

fn cookieHas(header: []const u8, key: []const u8, want: []const u8) bool {
    const got = cookieValue(header, key) orelse return false;
    if (got.len != want.len) return false;
    // Constant-time: this is the CSRF check, and a length-and-prefix leak is
    // exactly what makes such a token guessable.
    var diff: u8 = 0;
    for (got, want) |a, b| diff |= a ^ b;
    return diff == 0;
}

test "findParam pulls a value out of a query string" {
    try std.testing.expectEqualStrings("abc", findParam("code=abc&state=xyz", "code").?);
    try std.testing.expectEqualStrings("xyz", findParam("code=abc&state=xyz", "state").?);
    try std.testing.expect(findParam("code=abc", "state") == null);
}

test "cookieValue and cookieHas" {
    const h = "t27_state=deadbeef; t27_gh=gho_token";
    try std.testing.expectEqualStrings("deadbeef", cookieValue(h, "t27_state").?);
    try std.testing.expectEqualStrings("gho_token", cookieValue(h, "t27_gh").?);
    try std.testing.expect(cookieHas(h, "t27_state", "deadbeef"));
    try std.testing.expect(!cookieHas(h, "t27_state", "deadbeee"));
    try std.testing.expect(!cookieHas(h, "t27_state", "short"));
    try std.testing.expect(!cookieHas(h, "missing", "x"));
}
