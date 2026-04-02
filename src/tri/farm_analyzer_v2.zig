// @origin(spec:farm_analyzer_v2.tri) @regen(manual-impl)
//
// ═══════════════════════════════════════════════════════════════════════════════
// FARM ANALYZER V2 — Logs-Based Sacred Worker Analysis
// ═══════════════════════════════════════════════════════════════════════════════
//
// Proper logic for autonomous analysis of sacred workers:
// 1. Status taken only from fresh `railway logs` (step=... PPL=... lines)
// 2. Sacred worker can be restarted only if logs show a real error
//    (DatasetNotFound, OOM, panic, exception)
// 3. No API access to account (FARM-7/8) treated as "unmonitored"
// 4. DON'T consider sacred workers stalled while logs show growing `step=`
//
// φ² + 1/φ² = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const Allocator = std.mem.Allocator;

const RESET = "\x1b[0m";
const BOLD = "\x1b[1m";
const RED = "\x1b[31m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const DIM = "\x1b[2m";
const CYAN = "\x1b[36m";
const MAGENTA = "\x1b[35m";

/// Error categories for sacred workers
pub const ErrorCategory = enum(u8) {
    none, // No error
    dataset_not_found, // DatasetNotFound — fatal
    oom, // Out of Memory — fatal
    panic, // panic/abort — fatal
    exception, // exception — fatal
    timeout, // timeout — possibly recoverable
    network, // network error — possibly recoverable
    unknown, // unknown error
};

/// Result of sacred worker log analysis
pub const WorkerAnalysis = struct {
    name: []const u8,
    account: []const u8,
    // From logs
    latest_step: u32 = 0,
    latest_ppl: f32 = 999.0,
    latest_loss: f32 = 99.0,
    log_age_sec: i64 = 0, // age of latest log line (seconds)
    // Status
    is_training: bool = false, // has fresh step=... lines
    is_stalled: bool = false, // step not progressing >10 min
    error_category: ErrorCategory = .none,
    error_message: []const u8 = "",
    // Recommendation
    can_restart: bool = false,
    restart_reason: []const u8 = "",
};

/// Analyzes sacred worker logs and returns status
pub fn analyzeWorkerLogs(
    allocator: Allocator,
    log_json: []const u8,
    worker_name: []const u8,
    account_name: []const u8,
) !WorkerAnalysis {
    var result = WorkerAnalysis{
        .name = worker_name,
        .account = account_name,
    };

    const parsed = std.json.parseFromSlice(std.json.Value, allocator, log_json, .{}) catch {
        return result; // Return defaults on parsing error
    };
    defer parsed.deinit();

    const data = parsed.value.object.get("data") orelse return result;
    const logs_val = data.object.get("deploymentLogs") orelse return result;
    if (logs_val != .array) return result;

    const logs = logs_val.array.items;
    if (logs.len == 0) return result;

    // Iterate through logs from old to new (to find fresh metrics)
    var latest_step: u32 = 0;
    var latest_ppl: f32 = 999.0;
    var latest_loss: f32 = 99.0;
    var has_training_line = false; // has fresh step=... lines

    for (logs) |log_entry| {
        const msg = log_entry.object.get("message") orelse continue;
        if (msg != .string) continue;

        const line = msg.string;

        // Check for fatal errors
        if (detectFatalError(line)) |cat| {
            result.error_category = cat;
            result.error_message = line;
            result.can_restart = true; // Restart needed on fatal error
            return result;
        }

        // Parses training line: "step | loss | avg_loss | ppl | ..."
        if (parseTrainingLine(line)) |metrics| {
            if (metrics.step > latest_step) {
                latest_step = metrics.step;
                latest_ppl = metrics.ppl;
                latest_loss = metrics.loss;
                has_training_line = true;
            }
        }
    }

    result.latest_step = latest_step;
    result.latest_ppl = latest_ppl;
    result.latest_loss = latest_loss;
    result.is_training = has_training_line and latest_step > 0;

    // Check for stale logs (no fresh lines >10 min)
    if (logs.len > 0) {
        const last_log = logs[logs.len - 1];
        if (last_log.object.get("timestamp")) |ts| {
            if (ts == .integer) {
                const log_ts_ms = ts.integer;
                const now_ms = std.time.milliTimestamp();
                const age_ms = now_ms - log_ts_ms;
                result.log_age_sec = @divTrunc(age_ms, 1000);

                // Logs older than 10 min → possibly stalled
                result.is_stalled = result.is_training and result.log_age_sec > 600;
            }
        }
    }

    // Can restart only on explicit error
    result.can_restart = result.error_category != .none;

    return result;
}

/// Determines fatal error category in log line
fn detectFatalError(line: []const u8) ?ErrorCategory {
    // Dataset errors
    if (std.mem.indexOf(u8, line, "DatasetNotFound") != null or
        std.mem.indexOf(u8, line, "dataset not found") != null or
        std.mem.indexOf(u8, line, "FileNotFound") != null)
    {
        return .dataset_not_found;
    }

    // OOM errors
    if (std.mem.indexOf(u8, line, "Out of Memory") != null or
        std.mem.indexOf(u8, line, "OOM") != null or
        std.mem.indexOf(u8, line, "out of memory") != null or
        std.mem.indexOf(u8, line, "Cannot allocate") != null)
    {
        return .oom;
    }

    // Panic/abort
    if (std.mem.indexOf(u8, line, "panic") != null or
        std.mem.indexOf(u8, line, "PANIC") != null or
        std.mem.indexOf(u8, line, "abort") != null or
        std.mem.indexOf(u8, line, "ABORT") != null)
    {
        return .panic;
    }

    // Exception
    if (std.mem.indexOf(u8, line, "Exception") != null or
        std.mem.indexOf(u8, line, "exception") != null or
        std.mem.indexOf(u8, line, "Error:") != null)
    {
        return .exception;
    }

    // Timeout
    if (std.mem.indexOf(u8, line, "timeout") != null or
        std.mem.indexOf(u8, line, "TIMEOUT") != null)
    {
        return .timeout;
    }

    // Network
    if (std.mem.indexOf(u8, line, "Connection refused") != null or
        std.mem.indexOf(u8, line, "Network") != null)
    {
        return .network;
    }

    return null;
}

/// Metrics from training line
const TrainingMetrics = struct {
    step: u32,
    loss: f32,
    ppl: f32,
};

/// Parses training line: "step | loss | avg_loss | ppl | ..."
fn parseTrainingLine(line: []const u8) ?TrainingMetrics {
    // Must be at least 6 pipes
    var pipe_count: usize = 0;
    for (line) |c| {
        if (c == '|') pipe_count += 1;
    }
    if (pipe_count < 6) return null;

    // Split by '|'
    var columns: [8][]const u8 = undefined;
    var col_idx: usize = 0;
    var start: usize = 0;
    for (line, 0..) |c, ci| {
        if (c == '|') {
            if (col_idx < 8) {
                columns[col_idx] = std.mem.trim(u8, line[start..ci], &[_]u8{ ' ', '\t' });
                col_idx += 1;
            }
            start = ci + 1;
        }
    }
    // Last column
    if (col_idx < 8 and start < line.len) {
        columns[col_idx] = std.mem.trim(u8, line[start..], &[_]u8{ ' ', '\t' });
        col_idx += 1;
    }

    if (col_idx < 7) return null;

    const step = std.fmt.parseInt(u32, columns[0], 10) catch return null;
    const loss = std.fmt.parseFloat(f32, columns[1]) catch return null;
    const ppl = std.fmt.parseFloat(f32, columns[3]) catch return null;

    if (ppl <= 0 or loss <= 0) return null;

    return .{ .step = step, .loss = loss, .ppl = ppl };
}

/// Checks if Railway API is accessible for the account
pub fn checkAccountAccess(allocator: Allocator, account_suffix: []const u8) !bool {
    _ = allocator;
    _ = account_suffix;
    // TODO: Execute test GraphQL query
    // For now return true (assume access exists)
    return true;
}

/// Account status for dashboard
pub const AccountStatus = enum(u8) {
    monitored, // API accessible, logs readable
    unmonitored, // API unavailable (token expired/no project)
    api_error, // API error (error is reserved in Zig 0.15)
};

/// Account analysis result
pub const AccountAnalysis = struct {
    name: []const u8,
    suffix: []const u8,
    status: AccountStatus = .unmonitored,
    workers_total: usize = 0,
    workers_training: usize = 0,
    workers_stalled: usize = 0,
    workers_error: usize = 0,
    latest_step: u32 = 0,
    best_ppl: f32 = 999.0,
    best_worker: []const u8 = "",
};

/// Analyzes all farm accounts
pub fn analyzeFarmAccounts(
    allocator: Allocator,
    accounts: []const []const u8,
) ![]AccountAnalysis {
    var results = try std.ArrayList(AccountAnalysis).initCapacity(allocator, accounts.len);
    defer results.deinit();

    for (accounts) |acct_name| {
        const analysis = AccountAnalysis{
            .name = acct_name,
            .suffix = "",
            .status = .unmonitored, // By default — not monitored
        };
        try results.append(analysis);
    }

    return results.toOwnedSlice(allocator);
}

/// Returns human-readable status description
pub fn formatAccountStatus(status: AccountStatus) []const u8 {
    return switch (status) {
        .monitored => "✅ monitored",
        .unmonitored => "⚠️ unmonitored",
        .api_error => "❌ error",
    };
}

/// Returns human-readable error description
pub fn formatErrorCategory(cat: ErrorCategory) []const u8 {
    return switch (cat) {
        .none => "none",
        .dataset_not_found => "DatasetNotFound",
        .oom => "OOM",
        .panic => "panic",
        .exception => "exception",
        .timeout => "timeout",
        .network => "network",
        .unknown => "unknown",
    };
}

/// Formats worker analysis for dashboard
pub fn formatWorkerAnalysis(analysis: *const WorkerAnalysis) ![]const u8 {
    var buf = std.ArrayList(u8).init(std.heap.page_allocator);
    defer buf.deinit();

    const status_str = if (analysis.is_training) "🟢 training" else if (analysis.is_stalled) "🟡 stalled" else "🔴 idle";

    try buf.writer().print(
        \\{s}: {s}
        \\  step={d} PPL={d:.1} age={d}s
        \\  error={s}
        \\  can_restart={}
    , .{
        analysis.name,
        status_str,
        analysis.latest_step,
        analysis.latest_ppl,
        analysis.log_age_sec,
        formatErrorCategory(analysis.error_category),
        analysis.can_restart,
    });

    return buf.toOwnedSlice(std.heap.page_allocator);
}

// ═══════════════════════════════════════════════════════════════════════════════
// CLI COMMAND — tri farm analyze
// ═══════════════════════════════════════════════════════════════════════════════

const print = std.debug.print;

/// Launches farm analysis based on fresh logs via Railway API
/// Usage: tri farm analyze [--account <name>] [--worker <name>] [--sacred-only] [--json]
pub fn runAnalyzeCommand(allocator: Allocator, args: []const []const u8) !void {
    var filter_account: ?[]const u8 = null;
    var filter_worker: ?[]const u8 = null;
    var sacred_only = false;
    var json_output = false;

    // Parse arguments
    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        if (std.mem.eql(u8, args[i], "--account") and i + 1 < args.len) {
            i += 1;
            filter_account = args[i];
        } else if (std.mem.eql(u8, args[i], "--worker") and i + 1 < args.len) {
            i += 1;
            filter_worker = args[i];
        } else if (std.mem.eql(u8, args[i], "--sacred-only")) {
            sacred_only = true;
        } else if (std.mem.eql(u8, args[i], "--json")) {
            json_output = true;
        } else if (std.mem.eql(u8, args[i], "--help") or std.mem.eql(u8, args[i], "-h")) {
            printAnalyzeHelp();
            return;
        }
    }

    if (!json_output) {
        print("\n{s}🔍 FARM ANALYZER V2 — Logs-Based Sacred Worker Analysis{s}\n", .{ BOLD, RESET });
        print("{s}════════════════════════════════════════════════════════════{s}\n\n", .{ DIM, RESET });
    }

    // Import farm accounts module
    const farm_accounts_mod = @import("farm_accounts.zig");
    const RailwayApi = @import("railway_api.zig").RailwayApi;

    var acct_buf: [farm_accounts_mod.MAX_ACCOUNTS]farm_accounts_mod.Account = undefined;
    const acct_count = farm_accounts_mod.discoverAccounts(allocator, &acct_buf);
    defer farm_accounts_mod.deinitAccounts(allocator, &acct_buf, acct_count);

    if (acct_count == 0) {
        print("{s}⚠️  No Railway accounts found. Set RAILWAY_API_TOKEN in .env{s}\n", .{ YELLOW, RESET });
        return;
    }

    var total_workers: usize = 0;
    var total_training: usize = 0;
    var total_stalled: usize = 0;
    var total_error: usize = 0;
    var total_unmonitored: usize = 0;

    // Collect all results for summary
    var results = try std.ArrayList(WorkerAnalysis).initCapacity(allocator, 0);
    defer results.deinit(allocator);

    for (acct_buf[0..acct_count]) |acct| {
        // Account filter
        if (filter_account) |fa| {
            if (!std.mem.eql(u8, fa, acct.name) and !std.mem.eql(u8, fa, acct.suffix)) continue;
        }

        if (!json_output) {
            print("{s}=== {s} ==={s}\n", .{ BOLD, acct.name, RESET });
        }

        // Init Railway API
        var api = RailwayApi.initWithSuffix(allocator, acct.suffix) catch |err| {
            if (!json_output) {
                print("  {s}⚠️  API access failed: {s} → {s}{s}\n\n", .{ YELLOW, @errorName(err), formatAccountStatus(.unmonitored), RESET });
                total_unmonitored += 1;
            }
            continue;
        };
        defer api.deinit();

        // Get service instances
        const services_resp = api.getServiceInstances(acct.env_id) catch |err| {
            if (!json_output) {
                print("  {s}⚠️  API query failed: {s}{s}\n\n", .{ YELLOW, @errorName(err), RESET });
            }
            continue;
        };
        defer allocator.free(services_resp);

        const parsed = std.json.parseFromSlice(std.json.Value, allocator, services_resp, .{}) catch {
            if (!json_output) {
                print("  {s}⚠️  Invalid JSON response{s}\n\n", .{ YELLOW, RESET });
            }
            continue;
        };
        defer parsed.deinit();

        const items = getEdgesArrayRailway(parsed.value) orelse {
            if (!json_output) {
                print("  {s}⚠️  No services found{s}\n\n", .{ YELLOW, RESET });
            }
            continue;
        };

        // Process each service
        for (items) |edge| {
            const node = getJsonObjectRailway(edge, "node") orelse continue;
            const svc_name = getStringRailway(node, "serviceName");

            // Worker filter
            if (filter_worker) |fw| {
                if (!std.mem.eql(u8, fw, svc_name)) continue;
            }

            // Skip if not sacred (sacred-only mode)
            if (sacred_only and !isSacredWorker(svc_name)) continue;

            // Skip non-training services
            if (!isTrainingWorker(svc_name)) continue;

            total_workers += 1;

            // Get service ID for logs
            const svc_id = getStringRailway(node, "id");

            // Fetch deployment logs
            const logs_resp = api.getDeploymentLogs(svc_id, 100) catch |err| {
                if (!json_output) {
                    print("  {s}⚠️  {s}: logs fetch failed ({s}){s}\n", .{ YELLOW, svc_name, @errorName(err), RESET });
                }
                continue;
            };
            defer allocator.free(logs_resp);

            // Analyze logs
            const analysis = try analyzeWorkerLogs(allocator, logs_resp, svc_name, acct.name);
            try results.append(allocator, analysis);

            // Update totals
            if (analysis.is_training) total_training += 1;
            if (analysis.is_stalled) total_stalled += 1;
            if (analysis.error_category != .none) total_error += 1;

            // Display result
            if (!json_output) {
                const status_icon = if (analysis.is_training) "🟢" else if (analysis.is_stalled) "🟡" else if (analysis.error_category != .none) "🔴" else "⚪";
                const status_text = if (analysis.is_training) "training" else if (analysis.is_stalled) "stalled" else if (analysis.error_category != .none) "error" else "idle";
                const color = if (analysis.is_training) GREEN else if (analysis.is_stalled) YELLOW else RED;

                print("  {s} {s}{s}{s}", .{ status_icon, color, svc_name, RESET });
                padToName(svc_name.len, 20);
                print(" {s}{s}{s}", .{ color, status_text, RESET });

                if (analysis.latest_step > 0) {
                    print(" step={d}", .{analysis.latest_step});
                }
                if (analysis.latest_ppl < 900) {
                    print(" PPL={d:.1}", .{analysis.latest_ppl});
                }
                if (analysis.log_age_sec > 0) {
                    print(" age={d}s", .{analysis.log_age_sec});
                }
                if (analysis.error_category != .none) {
                    print(" [{s}]", .{formatErrorCategory(analysis.error_category)});
                }

                if (analysis.can_restart) {
                    print(" {s}[RESTART]{s}", .{ GREEN, RESET });
                }

                print("\n", .{});
            }
        }

        if (!json_output) {
            print("\n", .{});
        }
    }

    // Summary
    if (!json_output) {
        print("{s}════════════════════════════════════════════════════════════{s}\n", .{ DIM, RESET });
        print("{s}SUMMARY: {d} workers | 🟢 {d} training | 🟡 {d} stalled | 🔴 {d} error | ⚠️ {d} unmonitored{s}\n\n", .{
            BOLD, total_workers, total_training, total_stalled, total_error, total_unmonitored, RESET,
        });

        // Actionable recommendations
        if (total_error > 0) {
            print("{s}⚡ RECOMMENDED: Restart {d} workers with fatal errors{s}\n", .{ YELLOW, total_error, RESET });
            print("   Use: tri farm recycle --force\n\n", .{});
        } else if (total_stalled > 0) {
            print("{s}⚠️  NOTE: {d} workers stalled (no step growth in 10+ min){s}\n", .{ YELLOW, total_stalled, RESET });
            print("   Check logs manually before restarting\n\n", .{});
        } else if (total_training > 0) {
            print("{s}✅ All {d} sacred workers training normally{s}\n\n", .{ GREEN, total_training, RESET });
        }
    } else if (json_output) {
        // JSON output for programmatic use
        var json_buf = try std.ArrayList(u8).initCapacity(allocator, 0);
        defer json_buf.deinit(allocator);

        try json_buf.append(allocator, '{');
        try json_buf.writer(allocator).print(
            \\"total_workers":{d},"training":{d},"stalled":{d},"error":{d},"unmonitored":{d},"workers":[
        , .{ total_workers, total_training, total_stalled, total_error, total_unmonitored });

        for (results.items, 0..) |analysis, idx| {
            if (idx > 0) try json_buf.append(allocator, ',');
            try json_buf.writer(allocator).print(
                \\"name\\":\\"{s}\\",\\"account\\":\\"{s}\\",\\"step\\":{d},\\"ppl\\":{d:.1},\\"training\\":{s},\\"stalled\\":{s},\\"error\\":\\"{s}\\",\\"can_restart\\":{s}}}
            , .{
                analysis.name,
                analysis.account,
                analysis.latest_step,
                analysis.latest_ppl,
                if (analysis.is_training) "true" else "false",
                if (analysis.is_stalled) "true" else "false",
                formatErrorCategory(analysis.error_category),
                if (analysis.can_restart) "true" else "false",
            });
        }

        try json_buf.append(allocator, ']');
        try json_buf.append(allocator, '}');

        print("{s}\n", .{json_buf.items});
    }
}

fn printAnalyzeHelp() void {
    print(
        \\
        \\Usage: tri farm analyze [options]
        \\
        \\Analyzes sacred workers using FRESH Railway logs (not cached state).
        \\
        \\Options:
        \\  --account <name>   Filter by account name (e.g., FARM-2)
        \\  --worker <name>    Filter by worker name (e.g., hslm-w7-1)
        \\  --sacred-only     Only show sacred workers (r33, sacred-*)
        \\  --json            Output JSON for programmatic use
        \\  --help, -h        Show this help
        \\
        \\Status determination:
        \\  🟢 training   — Fresh step=... lines in logs (<10 min old)
        \\  🟡 stalled    — Training detected but step not growing (>10 min)
        \\  🔴 error      — Fatal error in logs (OOM, panic, DatasetNotFound)
        \\  ⚪ idle       — No training lines found
        \\  ⚠️  unmonitored — No API access to account
        \\
        \\Sacred worker restart rules:
        \\  ✅ CAN restart  — Fatal error visible (OOM, panic, exception)
        \\  ❌ DON'T restart — No error in logs, even if stalled
        \\
    , .{});
}

fn getJsonObjectRailway(val: std.json.Value, key: []const u8) ?std.json.Value {
    if (val != .object) return null;
    return val.object.get(key);
}

fn getStringRailway(val: std.json.Value, key: []const u8) []const u8 {
    if (val != .object) return "";
    const v = val.object.get(key) orelse return "";
    if (v != .string) return "";
    return v.string;
}

fn getEdgesArrayRailway(root: std.json.Value) ?[]std.json.Value {
    const data_val = getJsonObjectRailway(root, "data") orelse return null;
    const env_val = getJsonObjectRailway(data_val, "environment") orelse return null;
    const si_val = getJsonObjectRailway(env_val, "serviceInstances") orelse return null;
    const edges_val = getJsonObjectRailway(si_val, "edges") orelse return null;
    if (edges_val != .array) return null;
    return edges_val.array.items;
}

fn padToName(current: usize, target: usize) void {
    if (current >= target) return;
    var pad_i: usize = 0;
    while (pad_i < target - current) : (pad_i += 1) {
        print(" ", .{});
    }
}

/// Checks if worker is "sacred" (r33 or sacred-*)
fn isSacredWorker(name: []const u8) bool {
    if (std.mem.indexOf(u8, name, "r33") != null) return true;
    if (std.mem.indexOf(u8, name, "sacred-") != null) return true;
    if (std.mem.indexOf(u8, name, "hslm-r") != null) return true;
    return false;
}

/// Checks if service is training worker
fn isTrainingWorker(name: []const u8) bool {
    // hslm-wN, hslm-rN, r33-*, sacred-*
    if (std.mem.indexOf(u8, name, "hslm-") != null) return true;
    if (std.mem.indexOf(u8, name, "r33-") != null) return true;
    if (std.mem.indexOf(u8, name, "sacred-") != null) return true;
    return false;
}

// ═══════════════════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════════════════

test "analyzeWorkerLogs - training line" {
    const allocator = std.testing.allocator;
    const log_json =
        \\{"data":{"deploymentLogs":[
        \\  {"message":"    5000 |   5.8234 |   5.9100 |   338.45 |   0.001000 |   0.8234 |   1400","timestamp":12345000},
        \\  {"message":"    5001 |   5.8220 |   5.9080 |   338.30 |   0.001000 |   0.8230 |   1410","timestamp":12346000}
        \\]}}
    ;

    const result = try analyzeWorkerLogs(allocator, log_json, "hslm-w7-1", "FARM-2");
    try std.testing.expectEqual(@as(u32, 5001), result.latest_step);
    try std.testing.expect(result.is_training);
    try std.testing.expect(!result.is_stalled);
    try std.testing.expectEqual(.none, result.error_category);
    try std.testing.expect(!result.can_restart);
}

test "analyzeWorkerLogs - OOM error" {
    const allocator = std.testing.allocator;
    const log_json =
        \\{"data":{"deploymentLogs":[
        \\  {"message":"Out of Memory","timestamp":12345000}
        \\]}}
    ;

    const result = try analyzeWorkerLogs(allocator, log_json, "hslm-w7-2", "FARM-2");
    try std.testing.expectEqual(.oom, result.error_category);
    try std.testing.expect(result.can_restart);
}

test "parseTrainingLine - valid" {
    const line = "    5000 |   5.8234 |   5.9100 |   338.45 |   0.001000 |   0.8234 |   1400";
    const result = parseTrainingLine(line) orelse unreachable;
    try std.testing.expectEqual(@as(u32, 5000), result.step);
    try std.testing.expectApproxEqAbs(@as(f32, 5.8234), result.loss, 0.001);
    try std.testing.expectApproxEqAbs(@as(f32, 338.45), result.ppl, 0.01);
}

test "detectFatalError - panic" {
    const line = "thread 'main' panicked at 'src/main.rs:42:5'";
    const result = detectFatalError(line) orelse unreachable;
    try std.testing.expectEqual(.panic, result);
}

test "detectFatalError - OOM" {
    const line = "Out of Memory";
    const result = detectFatalError(line) orelse unreachable;
    try std.testing.expectEqual(.oom, result);
}

test "detectFatalError - no error" {
    const line = "    5000 |   5.8234 |   5.9100 |   338.45 |   0.001000 |   0.8234 |   1400";
    if (detectFatalError(line)) |_| {
        try std.testing.expect(false);
    }
}
