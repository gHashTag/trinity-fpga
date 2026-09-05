//! GitHub collaboration backend for the Spec Explorer.
//!
//! Lets a visitor connect their own GitHub account from t27.ai/#/specs, edit a
//! spec in the browser, and have the change land as a pull request authored by
//! them. Also receives GitHub webhooks so a failing spec can be turned into an
//! issue automatically.
//!
//! ## Why an OAuth App and not a GitHub App
//!
//! A GitHub App authenticates by signing a JWT with its RSA private key
//! (RS256), exchanging that for an installation token. Zig 0.16's std.crypto
//! ships `Certificate.rsa.PublicKey` but **no SecretKey** -- it can verify RSA
//! signatures and cannot produce them. Checked directly against the toolchain
//! rather than assumed; there is no RS256 signer in std to call.
//!
//! CLAUDE.md forbids shelling out to openssl or a Python helper, and vendoring
//! an RSA implementation to hold a production signing key is not a trade worth
//! making for this feature. So this is an **OAuth App**, which needs only a
//! client id/secret and one HTTPS POST -- all of which std does have.
//!
//! The practical difference is whose name is on the pull request. A GitHub App
//! opens PRs as a bot; an OAuth App opens them as the contributor. For a
//! corpus of specs people are proposing fixes to, the contributor's name is
//! the better answer anyway -- they get the attribution, and their own
//! permissions bound what the token can do.
//!
//! Webhook receipt needs only HMAC-SHA256, which std has, so that half is
//! unaffected by any of the above.
//!
//! ## Endpoints
//!
//!   GET  /health              liveness, no auth
//!   GET  /auth/github         redirect into GitHub's consent screen
//!   GET  /auth/callback       exchange ?code for a user access token
//!   POST /api/propose         branch + commit + PR, as the connected user
//!   POST /webhook             GitHub events, HMAC-verified
//!
//! ## Configuration (Railway variables)
//!
//!   GITHUB_CLIENT_ID          OAuth app client id
//!   GITHUB_CLIENT_SECRET      OAuth app client secret
//!   GITHUB_WEBHOOK_SECRET     shared secret for webhook HMAC
//!   PUBLIC_ORIGIN             e.g. https://t27-collab.up.railway.app
//!   ALLOWED_ORIGIN            e.g. https://t27.ai  (CORS)
//!   PORT                      injected by Railway

const std = @import("std");

pub const Config = struct {
    client_id: []const u8,
    client_secret: []const u8,
    webhook_secret: []const u8,
    public_origin: []const u8,
    allowed_origin: []const u8,
    port: u16,

    /// Missing configuration is fatal at boot rather than at first request:
    /// a service that starts and then 500s on every call looks healthy to
    /// Railway's restart policy and stays broken.
    ///
    /// 0.16 hands the environment in through `std.process.Init.environ_map`
    /// rather than exposing a global getter, so the map is a parameter.
    pub fn fromEnv(env: *std.process.Environ.Map) !Config {
        return .{
            .client_id = try need(env, "GITHUB_CLIENT_ID"),
            .client_secret = try need(env, "GITHUB_CLIENT_SECRET"),
            .webhook_secret = try need(env, "GITHUB_WEBHOOK_SECRET"),
            .public_origin = try need(env, "PUBLIC_ORIGIN"),
            .allowed_origin = env.get("ALLOWED_ORIGIN") orelse "https://t27.ai",
            .port = blk: {
                const p = env.get("PORT") orelse break :blk 8080;
                break :blk std.fmt.parseInt(u16, p, 10) catch 8080;
            },
        };
    }

    fn need(env: *std.process.Environ.Map, key: []const u8) ![]const u8 {
        return env.get(key) orelse {
            std.debug.print("github_collab: missing required env var {s}\n", .{key});
            return error.MissingConfig;
        };
    }
};

// ---------------------------------------------------------------------------
// Webhook signature
// ---------------------------------------------------------------------------

const HmacSha256 = std.crypto.auth.hmac.sha2.HmacSha256;

/// Verify GitHub's `X-Hub-Signature-256: sha256=<hex>` over the raw body.
///
/// Compared in constant time. A plain `mem.eql` here leaks how many leading
/// bytes matched, which is enough to forge a signature byte by byte given
/// enough attempts -- the whole point of the header is defeated by comparing
/// it carelessly.
pub fn verifySignature(secret: []const u8, body: []const u8, header: []const u8) bool {
    const prefix = "sha256=";
    if (!std.mem.startsWith(u8, header, prefix)) return false;
    const hex = header[prefix.len..];
    if (hex.len != HmacSha256.mac_length * 2) return false;

    var expected: [HmacSha256.mac_length]u8 = undefined;
    HmacSha256.create(&expected, body, secret);

    var got: [HmacSha256.mac_length]u8 = undefined;
    _ = std.fmt.hexToBytes(&got, hex) catch return false;

    return std.crypto.timing_safe.eql([HmacSha256.mac_length]u8, expected, got);
}

// ---------------------------------------------------------------------------
// OAuth
// ---------------------------------------------------------------------------

/// The consent URL a visitor is sent to.
///
/// `public_repo` only: enough to fork and open a pull request against a public
/// repo, and nothing more. Asking for `repo` would hand us write access to
/// every private repository the visitor owns, to do a job that never touches
/// one.
pub fn authorizeUrl(allocator: std.mem.Allocator, cfg: Config, state: []const u8) ![]u8 {
    return std.fmt.allocPrint(
        allocator,
        "https://github.com/login/oauth/authorize?client_id={s}&redirect_uri={s}/auth/callback&scope=public_repo&state={s}",
        .{ cfg.client_id, cfg.public_origin, state },
    );
}

pub const TokenResult = struct {
    access_token: []const u8,
    scope: []const u8,
};

/// Exchange the `?code` from the callback for a user access token.
pub fn exchangeCode(
    allocator: std.mem.Allocator,
    io: std.Io,
    cfg: Config,
    code: []const u8,
) !TokenResult {
    // 0.16 takes `io` on the Client itself, not on each fetch call.
    var client: std.http.Client = .{ .allocator = allocator, .io = io };
    defer client.deinit();

    const body = try std.fmt.allocPrint(
        allocator,
        "client_id={s}&client_secret={s}&code={s}&redirect_uri={s}/auth/callback",
        .{ cfg.client_id, cfg.client_secret, code, cfg.public_origin },
    );
    defer allocator.free(body);

    var response: std.Io.Writer.Allocating = .init(allocator);
    defer response.deinit();

    const res = try client.fetch(.{
        .location = .{ .url = "https://github.com/login/oauth/access_token" },
        .method = .POST,
        .payload = body,
        .extra_headers = &.{
            .{ .name = "accept", .value = "application/json" },
            .{ .name = "content-type", .value = "application/x-www-form-urlencoded" },
        },
        .response_writer = &response.writer,
    });
    if (res.status != .ok) return error.TokenExchangeFailed;

    const parsed = try std.json.parseFromSlice(
        struct { access_token: ?[]const u8 = null, scope: ?[]const u8 = null, @"error": ?[]const u8 = null },
        allocator,
        response.written(),
        .{ .ignore_unknown_fields = true },
    );
    defer parsed.deinit();

    // GitHub answers 200 with an `error` field rather than a 4xx when the code
    // is expired or already used, so status alone is not enough to trust it.
    if (parsed.value.@"error" != null) return error.TokenExchangeRejected;
    const tok = parsed.value.access_token orelse return error.TokenExchangeRejected;

    return .{
        .access_token = try allocator.dupe(u8, tok),
        .scope = try allocator.dupe(u8, parsed.value.scope orelse ""),
    };
}

// ---------------------------------------------------------------------------
// Pull requests
// ---------------------------------------------------------------------------

pub const Proposal = struct {
    owner: []const u8,
    repo: []const u8,
    /// Path inside the repo, e.g. specs/demos/hello_world.t27
    path: []const u8,
    /// Full new file contents.
    content: []const u8,
    title: []const u8,
    body: []const u8,
    base: []const u8 = "main",
};

/// Branch name for a proposal.
///
/// Derived from the path so two edits to different specs never collide, with
/// everything outside [a-z0-9] flattened to '-'. Git refs reject a great many
/// characters and a spec path contains several of them.
pub fn branchName(allocator: std.mem.Allocator, path: []const u8, nonce: u64) ![]u8 {
    var buf: std.ArrayList(u8) = .empty;
    defer buf.deinit(allocator);
    try buf.appendSlice(allocator, "spec-edit/");
    for (path) |c| {
        const lower = std.ascii.toLower(c);
        try buf.append(allocator, if (std.ascii.isAlphanumeric(lower)) lower else '-');
    }
    // Zig 0.16's unmanaged ArrayList has no `.writer(allocator)`; format the
    // suffix separately and append it.
    var num: [24]u8 = undefined;
    const suffix = try std.fmt.bufPrint(&num, "-{d}", .{nonce});
    try buf.appendSlice(allocator, suffix);
    return buf.toOwnedSlice(allocator);
}

/// One authenticated call to api.github.com, returning the raw body.
///
/// Every GitHub write below is the same shape -- POST some JSON with a bearer
/// token -- so it is worth having once rather than five times.
fn api(
    allocator: std.mem.Allocator,
    io: std.Io,
    token: []const u8,
    method: std.http.Method,
    url: []const u8,
    payload: ?[]const u8,
) ![]u8 {
    var client: std.http.Client = .{ .allocator = allocator, .io = io };
    defer client.deinit();

    const auth = try std.fmt.allocPrint(allocator, "Bearer {s}", .{token});
    defer allocator.free(auth);

    var response: std.Io.Writer.Allocating = .init(allocator);
    errdefer response.deinit();

    const res = try client.fetch(.{
        .location = .{ .url = url },
        .method = method,
        .payload = payload,
        .extra_headers = &.{
            .{ .name = "authorization", .value = auth },
            .{ .name = "accept", .value = "application/vnd.github+json" },
            .{ .name = "x-github-api-version", .value = "2022-11-28" },
            // GitHub rejects API requests with no user agent.
            .{ .name = "user-agent", .value = "t27-spec-explorer" },
            .{ .name = "content-type", .value = "application/json" },
        },
        .response_writer = &response.writer,
    });

    switch (res.status) {
        .ok, .created => return response.toOwnedSlice(),
        .unauthorized, .forbidden => return error.GitHubUnauthorized,
        .not_found => return error.GitHubNotFound,
        // 422 is what GitHub returns for "branch already exists" and "no diff
        // between base and head" -- both are user-visible states, not bugs.
        .unprocessable_entity => return error.GitHubUnprocessable,
        else => return error.GitHubRequestFailed,
    }
}

/// Base-64 of the file content, which is the only encoding the contents API
/// accepts for a write.
fn b64(allocator: std.mem.Allocator, bytes: []const u8) ![]u8 {
    const enc = std.base64.standard.Encoder;
    const out = try allocator.alloc(u8, enc.calcSize(bytes.len));
    // encode() returns a const view of `out`; hand back the mutable buffer we
    // own so the caller can free it.
    _ = enc.encode(out, bytes);
    return out;
}

pub const PrResult = struct {
    url: []const u8,
    number: u64,
};

/// Branch, commit, pull request -- as the connected user.
///
/// Deliberately against the upstream repo rather than a fork: the OAuth scope
/// is `public_repo`, so this succeeds for anyone with push access and fails
/// cleanly with GitHubUnauthorized for anyone without. Handling the fork dance
/// would mean creating repositories under a visitor's account, which is a much
/// larger thing to do on someone's behalf than opening one pull request.
pub fn openPullRequest(
    allocator: std.mem.Allocator,
    io: std.Io,
    token: []const u8,
    p: Proposal,
    nonce: u64,
) !PrResult {
    // 1. Resolve the base branch head.
    const ref_url = try std.fmt.allocPrint(
        allocator,
        "https://api.github.com/repos/{s}/{s}/git/ref/heads/{s}",
        .{ p.owner, p.repo, p.base },
    );
    defer allocator.free(ref_url);
    const ref_body = try api(allocator, io, token, .GET, ref_url, null);
    defer allocator.free(ref_body);

    const ref_parsed = try std.json.parseFromSlice(
        struct { object: struct { sha: []const u8 } },
        allocator,
        ref_body,
        .{ .ignore_unknown_fields = true },
    );
    defer ref_parsed.deinit();
    const base_sha = ref_parsed.value.object.sha;

    // 2. Create the branch.
    const branch = try branchName(allocator, p.path, nonce);
    defer allocator.free(branch);

    const refs_url = try std.fmt.allocPrint(
        allocator,
        "https://api.github.com/repos/{s}/{s}/git/refs",
        .{ p.owner, p.repo },
    );
    defer allocator.free(refs_url);

    const new_ref = try std.fmt.allocPrint(
        allocator,
        "{{\"ref\":\"refs/heads/{s}\",\"sha\":\"{s}\"}}",
        .{ branch, base_sha },
    );
    defer allocator.free(new_ref);
    const ref_res = try api(allocator, io, token, .POST, refs_url, new_ref);
    allocator.free(ref_res);

    // 3. Commit the file. The contents API needs the blob sha of what it is
    //    replacing, so read it first; a missing file means a new one, which is
    //    also fine.
    const contents_url = try std.fmt.allocPrint(
        allocator,
        "https://api.github.com/repos/{s}/{s}/contents/{s}",
        .{ p.owner, p.repo, p.path },
    );
    defer allocator.free(contents_url);

    var existing_sha: ?[]const u8 = null;
    var existing_owned: ?[]u8 = null;
    defer if (existing_owned) |e| allocator.free(e);
    if (api(allocator, io, token, .GET, contents_url, null)) |cur| {
        existing_owned = cur;
        const cur_parsed = std.json.parseFromSlice(
            struct { sha: []const u8 },
            allocator,
            cur,
            .{ .ignore_unknown_fields = true },
        ) catch null;
        if (cur_parsed) |cp| {
            defer cp.deinit();
            existing_sha = try allocator.dupe(u8, cp.value.sha);
        }
    } else |_| {}
    defer if (existing_sha) |s| allocator.free(s);

    const encoded = try b64(allocator, p.content);
    defer allocator.free(encoded);

    const commit_body = if (existing_sha) |sha| try std.fmt.allocPrint(
        allocator,
        "{{\"message\":{f},\"content\":\"{s}\",\"branch\":\"{s}\",\"sha\":\"{s}\"}}",
        .{ std.json.fmt(p.title, .{}), encoded, branch, sha },
    ) else try std.fmt.allocPrint(
        allocator,
        "{{\"message\":{f},\"content\":\"{s}\",\"branch\":\"{s}\"}}",
        .{ std.json.fmt(p.title, .{}), encoded, branch },
    );
    defer allocator.free(commit_body);

    const commit_res = try api(allocator, io, token, .PUT, contents_url, commit_body);
    allocator.free(commit_res);

    // 4. Open the pull request.
    const pulls_url = try std.fmt.allocPrint(
        allocator,
        "https://api.github.com/repos/{s}/{s}/pulls",
        .{ p.owner, p.repo },
    );
    defer allocator.free(pulls_url);

    const pr_body = try std.fmt.allocPrint(
        allocator,
        "{{\"title\":{f},\"body\":{f},\"head\":\"{s}\",\"base\":\"{s}\"}}",
        .{ std.json.fmt(p.title, .{}), std.json.fmt(p.body, .{}), branch, p.base },
    );
    defer allocator.free(pr_body);

    const pr_res = try api(allocator, io, token, .POST, pulls_url, pr_body);
    defer allocator.free(pr_res);

    const pr_parsed = try std.json.parseFromSlice(
        struct { html_url: []const u8, number: u64 },
        allocator,
        pr_res,
        .{ .ignore_unknown_fields = true },
    );
    defer pr_parsed.deinit();

    return .{
        .url = try allocator.dupe(u8, pr_parsed.value.html_url),
        .number = pr_parsed.value.number,
    };
}

test {
    // Zig only analyses functions something references. `exchangeCode` and
    // `Config.fromEnv` have no unit test (both need network or environment),
    // so without this they would ship never having been type-checked at all.
    std.testing.refAllDecls(@This());
}

test "branchName flattens a spec path into a legal ref" {
    const a = std.testing.allocator;
    const b = try branchName(a, "specs/demos/hello_world.t27", 42);
    defer a.free(b);
    try std.testing.expectEqualStrings("spec-edit/specs-demos-hello-world-t27-42", b);
}

test "verifySignature accepts a correct mac and rejects a tampered one" {
    const secret = "it's a secret to everybody";
    const body = "{\"action\":\"opened\"}";
    var mac: [HmacSha256.mac_length]u8 = undefined;
    HmacSha256.create(&mac, body, secret);

    var header: [7 + HmacSha256.mac_length * 2]u8 = undefined;
    const h = try std.fmt.bufPrint(&header, "sha256={x}", .{mac});

    try std.testing.expect(verifySignature(secret, body, h));
    try std.testing.expect(!verifySignature(secret, "{\"action\":\"closed\"}", h));
    try std.testing.expect(!verifySignature("wrong secret", body, h));
    // Shape failures must be rejected, not crash.
    try std.testing.expect(!verifySignature(secret, body, "sha1=abc"));
    try std.testing.expect(!verifySignature(secret, body, "sha256=tooshort"));
}

test "authorizeUrl asks for public_repo and nothing wider" {
    const a = std.testing.allocator;
    const cfg: Config = .{
        .client_id = "cid",
        .client_secret = "shh",
        .webhook_secret = "shh",
        .public_origin = "https://example.test",
        .allowed_origin = "https://t27.ai",
        .port = 8080,
    };
    const url = try authorizeUrl(a, cfg, "nonce123");
    defer a.free(url);
    try std.testing.expect(std.mem.indexOf(u8, url, "scope=public_repo") != null);
    // `repo` would grant private-repo write; make sure it never creeps in.
    try std.testing.expect(std.mem.indexOf(u8, url, "scope=repo") == null);
    try std.testing.expect(std.mem.indexOf(u8, url, "state=nonce123") != null);
}
