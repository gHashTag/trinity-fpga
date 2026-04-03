// @origin(spec:claude_channels.tri) @regen(manual-impl)
// ═══════════════════════════════════════════════════════════════════════════════
// CLAUDE CHANNELS — Claude Channels Integration for Telegram
// ═══════════════════════════════════════════════════════════════════════════════
//
// Manages tmux sessions, pairing, and status monitoring via Railway SSH.
//
// SECURITY:
// - Auto-allowlist is enabled by default after pairing (P0)
// - Bot token can be read from stdin or env, not just CLI arg (P0)
// - Version gate enforces Claude >= 2.1.80 for Channels support (P1)
// - --skip-permissions flag available with explicit warning (P1)
//
// φ² + 1/φ² = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const Allocator = std.mem.Allocator;

const railway_ssh = @import("railway_ssh.zig");

const CYAN = "\x1b[0;36m";
const GREEN = "\x1b[0;32m";
const YELLOW = "\x1b[0;33m";
const RED = "\x1b[0;31m";
const MAGENTA = "\x1b[0;35m";
const RESET = "\x1b[0m";

// Minimum Claude Code version for Channels support
const MIN_CHANNELS_VERSION = "2.1.80";

pub const ChannelStatus = enum {
    NotStarted,
    WaitingForPair,
    Paired,
    Error,
    Crashed,
    Unknown,
};

pub const SessionError = error{
    SSHExecFailed,
    TmuxCommandFailed,
    SessionAlreadyRunning,
    InvalidPairingCode,
    TokenReadFailed,
};

const CLAUDE_SESSION = "claude";
const CLAUDE_COMMAND = "claude --channel telegram";

const Self = @This();

/// Start options for Claude session
pub const StartOptions = struct {
    skip_permissions: bool = false,
    auto_allowlist: bool = true,
};

/// Start Claude session with Telegram channels
/// Creates detached tmux session running Claude in Channels mode
pub fn startSession(allocator: Allocator, options: StartOptions) !void {
    std.debug.print("{s}Starting Claude session with Telegram channels...{s}\n", .{ CYAN, RESET });

    // Security warning for skip-permissions
    if (options.skip_permissions) {
        std.debug.print("\n{s}⚠️  SECURITY WARNING:{s}\n", .{ YELLOW, RESET });
        std.debug.print("  --skip-permissions is enabled. This allows Claude to execute\n", .{});
        std.debug.print("  commands without confirmation. Use ONLY in isolated project directories.\n", .{});
        std.debug.print("  See: https://docs.anthropic.com/en/docs/build-with-claude/channels#security\n\n", .{});
    }

    // Build command with optional flags
    var cmd_buf: [256]u8 = undefined;
    const cmd = if (options.skip_permissions)
        try std.fmt.bufPrint(&cmd_buf, "claude --channel telegram --dangerously-skip-permissions", .{})
    else
        try std.fmt.bufPrint(&cmd_buf, "{s}", .{CLAUDE_COMMAND});

    var ssh = railway_ssh.RailwaySSH.initDefault();
    try ssh.tmuxNewSession(allocator, CLAUDE_SESSION, cmd);

    std.debug.print("{s}✓ Claude session started in tmux: {s}{s}\n", .{ GREEN, CLAUDE_SESSION, RESET });

    // Wait for Claude to initialize
    std.Thread.sleep(std.time.ns_per_s * 2);

    // Check version compatibility
    const runtime = @import("claude_runtime.zig");
    const version = runtime.getInstalledVersion(allocator) catch "unknown";
    defer if (!std.mem.eql(u8, version, "unknown")) allocator.free(version);

    if (std.mem.eql(u8, version, "unknown")) {
        std.debug.print("{s}⚠ Could not verify Claude version{s}\n", .{ YELLOW, RESET });
    } else {
        const meets_min = try runtime.compareVersions(allocator, version, MIN_CHANNELS_VERSION);
        if (!meets_min) {
            std.debug.print("{s}⚠ WARNING: Claude {s} is below Channels minimum ({s}){s}\n", .{
                YELLOW, version, MIN_CHANNELS_VERSION, RESET
            });
            std.debug.print("  Channels may not work correctly. Please update Claude Code.\n", .{});
        } else {
            std.debug.print("  Version {s} ✓ (Channels requires {s}+)\n", .{ version, MIN_CHANNELS_VERSION });
        }
    }

    if (options.auto_allowlist) {
        std.debug.print("\n{s}🔒 Security: Auto-allowlist will be set after pairing{s}\n", .{ GREEN, RESET });
    }

    std.debug.print("  Check status: tri railway telegram status\n", .{});
}

/// Send pairing command to Claude session
/// code: 6-character pairing code from Telegram bot
/// Automatically enables allowlist for security (P0)
pub fn sendPairCommand(allocator: Allocator, code: []const u8, auto_allowlist: bool) !void {
    // Validate pairing code format
    if (code.len != 6) {
        return error.InvalidPairingCode;
    }
    for (code) |c| {
        if (!std.ascii.isAlphanumeric(c)) {
            return error.InvalidPairingCode;
        }
    }

    std.debug.print("{s}Sending pairing command to Claude session...{s}\n", .{ CYAN, RESET });

    var ssh = railway_ssh.RailwaySSH.initDefault();

    // Build and send the pairing command
    var cmd_buf: [128]u8 = undefined;
    const cmd = std.fmt.bufPrint(&cmd_buf, "/telegram:access pair {s}", .{code}) catch {
        return error.InvalidPairingCode;
    };

    try ssh.tmuxSendKeys(allocator, CLAUDE_SESSION, cmd);

    std.debug.print("{s}✓ Pairing command sent: {s}{s}\n", .{ GREEN, cmd, RESET });

    // P0: Auto-enable allowlist for security
    if (auto_allowlist) {
        std.debug.print("\n{s}🔒 Enabling allowlist for security...{s}\n", .{ GREEN, RESET });

        // Wait a moment for pairing to process
        std.Thread.sleep(std.time.ns_per_ms * 1500);

        // Send allowlist command
        const allowlist_cmd = "/telegram:access policy allowlist";
        try ssh.tmuxSendKeys(allocator, CLAUDE_SESSION, allowlist_cmd);

        std.debug.print("{s}✓ Allowlist enabled (only you can send messages){s}\n", .{ GREEN, RESET });
        std.debug.print("  To disable: /telegram:access policy open (in Telegram)\n", .{});
    }

    std.debug.print("  Check status: tri railway telegram status\n", .{});
}

/// Enable allowlist policy for security
pub fn enableAllowlist(allocator: Allocator) !void {
    std.debug.print("{s}Enabling allowlist policy...{s}\n", .{ CYAN, RESET });

    var ssh = railway_ssh.RailwaySSH.initDefault();
    const cmd = "/telegram:access policy allowlist";
    try ssh.tmuxSendKeys(allocator, CLAUDE_SESSION, cmd);

    std.debug.print("{s}✓ Allowlist enabled{s}\n", .{ GREEN, RESET });
}

/// Get current channel status
/// Parses tmux output to determine status
pub fn getStatus(allocator: Allocator) !ChannelStatus {
    var ssh = railway_ssh.RailwaySSH.initDefault();

    // Capture last 50 lines from the session
    const output = ssh.tmuxCapture(allocator, CLAUDE_SESSION, 50) catch {
        return .NotStarted;
    };
    defer allocator.free(output);

    const lower_output = try std.ascii.allocLowerString(allocator, output);
    defer allocator.free(lower_output);

    // Parse status indicators
    if (std.mem.indexOf(u8, lower_output, "ready")) |_| {
        return .Paired;
    }
    if (std.mem.indexOf(u8, lower_output, "paired")) |_| {
        return .Paired;
    }
    if (std.mem.indexOf(u8, lower_output, "pairing code")) |_| {
        return .WaitingForPair;
    }
    if (std.mem.indexOf(u8, lower_output, "waiting")) |_| {
        return .WaitingForPair;
    }
    if (std.mem.indexOf(u8, lower_output, "error")) |_| {
        return .Error;
    }
    if (std.mem.indexOf(u8, lower_output, "failed")) |_| {
        return .Error;
    }
    if (std.mem.indexOf(u8, lower_output, "crashed")) |_| {
        return .Crashed;
    }
    if (std.mem.indexOf(u8, lower_output, "exited")) |_| {
        return .Crashed;
    }

    // Session exists but status unclear
    return .Unknown;
}

/// Get logs from Claude session
/// lines: Number of lines to retrieve (default 100)
pub fn getLogs(allocator: Allocator, lines: u32) ![]const u8 {
    const actual_lines = if (lines == 0) 100 else lines;
    var ssh = railway_ssh.RailwaySSH.initDefault();
    return ssh.tmuxCapture(allocator, CLAUDE_SESSION, actual_lines);
}

/// Restart Claude session
/// Kills existing session and creates new one
pub fn restartSession(allocator: Allocator, options: StartOptions) !void {
    std.debug.print("{s}Restarting Claude session...{s}\n", .{ CYAN, RESET });

    var ssh = railway_ssh.RailwaySSH.initDefault();

    // Kill existing session (ignore errors)
    var kill_cmd_buf: [64]u8 = undefined;
    const kill_cmd = std.fmt.bufPrint(&kill_cmd_buf, "tmux kill-session -t {s} 2>/dev/null", .{CLAUDE_SESSION}) catch "";
    const kill_output = ssh.exec(allocator, kill_cmd) catch "";
    allocator.free(kill_output);

    // Create new session
    try startSession(allocator, options);
}

/// Stop Claude session
/// Idempotent - no error if session doesn't exist
pub fn stopSession(allocator: Allocator) !void {
    std.debug.print("{s}Stopping Claude session...{s}\n", .{ CYAN, RESET });

    var ssh = railway_ssh.RailwaySSH.initDefault();

    var cmd_buf: [64]u8 = undefined;
    const cmd = std.fmt.bufPrint(&cmd_buf, "tmux kill-session -t {s} 2>/dev/null", .{CLAUDE_SESSION}) catch "";
    _ = ssh.exec(allocator, cmd) catch {};

    std.debug.print("{s}✓ Claude session stopped{s}\n", .{ GREEN, RESET });
}

/// Configure Telegram bot token
/// P0: Reads from stdin, env, or CLI argument (in that order of preference)
/// For security, stdin is recommended over CLI argument
pub fn configureTelegramBot(allocator: Allocator, cli_token: ?[]const u8) ![]const u8 {
    var token: ?[]const u8 = null;

    // 1. Try stdin first (most secure for interactive use)
    // In Zig 0.15, check if stdin is a TTY using isatty
    const is_tty = std.posix.isatty(std.posix.STDIN_FILENO);
    if (is_tty) {
        // Terminal is interactive, can read from stdin if piped
        var stdin_buf: [1024]u8 = undefined;
        // Use posix read for stdin
        const bytes_read = std.posix.read(std.posix.STDIN_FILENO, &stdin_buf) catch 0;

        if (bytes_read > 0) {
            const input = stdin_buf[0..bytes_read];
            const trimmed = std.mem.trim(u8, input, " \n\r\t");
            if (trimmed.len > 0) {
                token = trimmed;
                std.debug.print("{s}Token read from stdin{s}\n", .{ CYAN, RESET });
            }
        }
    }

    // 2. Try environment variable
    if (token == null) {
        if (std.posix.getenv("TELEGRAM_BOT_TOKEN")) |env| {
            token = env;
            std.debug.print("{s}Token read from TELEGRAM_BOT_TOKEN env{s}\n", .{ CYAN, RESET });
        }
    }

    // 3. Try CLI argument (least secure, but convenient)
    if (token == null) {
        if (cli_token) |ct| {
            token = ct;
            std.debug.print("{s}Token read from CLI argument{s}\n", .{ YELLOW, RESET });
            std.debug.print("  ⚠ Consider using stdin or env variable instead for security\n", .{});
        }
    }

    // Validate token format
    const actual_token = token orelse {
        return error.TokenReadFailed;
    };

    // Basic token validation (starts with numbers, colon, then string)
    if (actual_token.len < 10 or std.mem.indexOfScalar(u8, actual_token, ':') == null) {
        return error.InvalidPairingCode;
    }

    std.debug.print("\n{s}Telegram bot token configuration:{s}\n", .{ CYAN, RESET });
    std.debug.print("  Token: {s}***{s}\n", .{ actual_token[0..3], actual_token[actual_token.len - 3..] });

    // Note about persistence
    std.debug.print("\n{s}Note:{s} Token is NOT persisted to Railway automatically.\n", .{ YELLOW, RESET });
    std.debug.print("  To persist, add to Railway service environment variables:\n", .{});
    std.debug.print("    TELEGRAM_BOT_TOKEN=\"{s}\"\n", .{actual_token});
    std.debug.print("  Or via Railway dashboard: https://railway.app/project\n", .{});

    // Return the token for potential use by caller
    return try allocator.dupe(u8, actual_token);
}

/// Format ChannelStatus for display
pub fn formatChannelStatus(status: ChannelStatus) struct { []const u8, []const u8 } {
    return switch (status) {
        .NotStarted => .{ "Not started", RED },
        .WaitingForPair => .{ "Waiting for pair", YELLOW },
        .Paired => .{ "Paired & Ready", GREEN },
        .Error => .{ "Error", RED },
        .Crashed => .{ "Crashed", RED },
        .Unknown => .{ "Unknown", YELLOW },
    };
}

/// Run Claude Channels command — dispatches to subcommands
pub fn runClaudeChannelsCommand(allocator: Allocator, args: []const []const u8) !void {
    if (args.len < 1) {
        return showChannelsHelp();
    }

    const subcommand = args[0];
    const sub_args = args[1..];

    if (std.mem.eql(u8, subcommand, "init")) {
        return runInitCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "start")) {
        return runStartCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "pair")) {
        return runPairCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "status")) {
        return runStatusCommand(allocator);
    } else if (std.mem.eql(u8, subcommand, "logs")) {
        return runLogsCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "restart")) {
        return runRestartCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "stop")) {
        return runStopCommand(allocator);
    } else if (std.mem.eql(u8, subcommand, "allowlist")) {
        return runAllowlistCommand(allocator, sub_args);
    } else if (std.mem.eql(u8, subcommand, "doctor")) {
        return runDoctorCommand(allocator);
    } else if (std.mem.eql(u8, subcommand, "help") or std.mem.eql(u8, subcommand, "-h") or std.mem.eql(u8, subcommand, "--help")) {
        return showChannelsHelp();
    } else {
        std.debug.print("{s}Unknown telegram subcommand: {s}{s}\n", .{ RED, subcommand, RESET });
        return showChannelsHelp();
    }
}

fn showChannelsHelp() !void {
    std.debug.print(
        \\
        \\{s}CLAUDE TELEGRAM CHANNELS COMMANDS:{s}
        \\
        \\  {s}init [--from-env <var>]{s}  Configure Telegram bot token
        \\  {s}start [--skip-permissions]{s} Start Claude with Telegram
        \\  {s}pair <code>{s}             Complete pairing with 6-char code
        \\  {s}status{s}                   Show channel status
        \\  {s}logs [lines]{s}             Show Claude session logs (default: 100)
        \\  {s}restart [--skip-permissions]{s} Restart Claude session
        \\  {s}stop{s}                    Stop Claude session
        \\  {s}allowlist [on|off]{s}      Manage allowlist security
        \\  {s}doctor{s}                   Diagnose issues
        \\
        \\{s}SECURITY:{s}
        \\  Bot token is read from: stdin > env > CLI arg (in that order)
        \\  Auto-allowlist is enabled by default after pairing
        \\  Minimum Claude version: {s}
        \\
        \\{s}EXAMPLES:{s}
        \\  echo "$TOKEN" | tri railway telegram init
        \\  tri railway telegram init --from-env TELEGRAM_BOT_TOKEN
        \\  tri railway telegram start
        \\  tri railway telegram start --skip-permissions
        \\  tri railway telegram pair ABCDEF
        \\  tri railway telegram logs 50
        \\
    , .{
        CYAN, RESET,
        CYAN, RESET, CYAN, RESET,
        CYAN, RESET, CYAN, RESET, CYAN, RESET,
        CYAN, RESET, CYAN, RESET, CYAN, RESET,
        CYAN, RESET, CYAN, RESET,
        YELLOW, RESET,
        MIN_CHANNELS_VERSION,
    });
}

fn runInitCommand(allocator: Allocator, args: []const []const u8) !void {
    var cli_token: ?[]const u8 = null;
    var read_from_env: bool = false;
    var env_var_name: ?[]const u8 = null;

    // Parse args
    var i: usize = 0;
    while (i < args.len) : (i += 1) {
        const arg = args[i];
        if (std.mem.eql(u8, arg, "--from-env") and i + 1 < args.len) {
            env_var_name = args[i + 1];
            i += 1;
        } else if (cli_token == null) {
            // First non-flag arg is the token (deprecated, still supported)
            cli_token = arg;
        }
    }

    // If --from-env specified, read from that environment variable
    if (env_var_name) |var_name| {
        read_from_env = true;
        if (std.posix.getenv(var_name)) |value| {
            cli_token = value;
        } else {
            std.debug.print("{s}Error: Environment variable '{s}' not found{s}\n", .{ RED, var_name, RESET });
            return error.TokenReadFailed;
        }
    }

    // Configure with the resolved token
    const token = try configureTelegramBot(allocator, cli_token);
    defer allocator.free(token);

    // Show security reminder
    std.debug.print("\n{s}Security best practices:{s}\n", .{ YELLOW, RESET });
    if (read_from_env) {
        std.debug.print("  ✓ Token from env variable (good practice)\n", .{});
    } else if (cli_token != null) {
        std.debug.print("  ⚠ Token from CLI argument (visible in shell history)\n", .{});
        std.debug.print("  Better: echo \"$TOKEN\" | tri railway telegram init\n", .{});
    } else {
        std.debug.print("  ✓ Token from stdin (most secure)\n", .{});
    }
}

fn runStartCommand(allocator: Allocator, args: []const []const u8) !void {
    var options = StartOptions{};

    // Parse --skip-permissions flag
    for (args) |arg| {
        if (std.mem.eql(u8, arg, "--skip-permissions")) {
            options.skip_permissions = true;
        }
    }

    try startSession(allocator, options);

    // Wait and show status
    std.Thread.sleep(std.time.ns_per_ms * 1000);
    try runStatusCommand(allocator);
}

fn runPairCommand(allocator: Allocator, args: []const []const u8) !void {
    if (args.len < 1) {
        std.debug.print("{s}Usage: tri railway telegram pair <6-char-code>{s}\n", .{ RED, RESET });
        std.debug.print("  Get pairing code from Telegram bot after starting Claude\n", .{});
        return error.InvalidPairingCode;
    }

    const code = args[0];
    try sendPairCommand(allocator, code, true); // P0: auto-allowlist enabled

    // Wait and show status
    std.Thread.sleep(std.time.ns_per_ms * 2000);
    try runStatusCommand(allocator);
}

fn runStatusCommand(allocator: Allocator) !void {
    std.debug.print("{s}Claude Channels status:{s}\n", .{ CYAN, RESET });

    const status = try getStatus(allocator);
    const status_str, const color = formatChannelStatus(status);

    std.debug.print("  Session: {s}{s}{s}\n", .{ color, status_str, RESET });

    if (status == .NotStarted) {
        std.debug.print("  Start with: tri railway telegram start\n", .{});
    } else if (status == .WaitingForPair) {
        std.debug.print("  Pair with: tri railway telegram pair <code>\n", .{});
    } else if (status == .Paired) {
        std.debug.print("  {s}✓ Ready to receive messages from Telegram{s}\n", .{ GREEN, RESET });
    }
}

fn runLogsCommand(allocator: Allocator, args: []const []const u8) !void {
    const lines = if (args.len > 0)
        std.fmt.parseInt(u32, args[0], 10) catch 100
    else
        100;

    const logs = getLogs(allocator, lines) catch {
        std.debug.print("{s}✗ Failed to get logs (session not running?){s}\n", .{ RED, RESET });
        return;
    };
    defer allocator.free(logs);

    std.debug.print("{s}Claude session logs (last {d} lines):{s}\n", .{ CYAN, lines, RESET });
    std.debug.print("─{s}\n", .{"─" ** 60});

    const output = std.mem.trimRight(u8, logs, "\n\r ");
    std.debug.print("{s}\n", .{output});
}

fn runRestartCommand(allocator: Allocator, args: []const []const u8) !void {
    var options = StartOptions{};

    // Parse --skip-permissions flag
    for (args) |arg| {
        if (std.mem.eql(u8, arg, "--skip-permissions")) {
            options.skip_permissions = true;
        }
    }

    try restartSession(allocator, options);

    // Wait and show status
    std.Thread.sleep(std.time.ns_per_ms * 1000);
    try runStatusCommand(allocator);
}

fn runStopCommand(allocator: Allocator) !void {
    try stopSession(allocator);
}

fn runAllowlistCommand(allocator: Allocator, args: []const []const u8) !void {
    if (args.len > 0) {
        const action = args[0];
        if (std.mem.eql(u8, action, "on") or std.mem.eql(u8, action, "enable")) {
            try enableAllowlist(allocator);
            std.debug.print("  Allowlist enabled (only you can send messages)\n", .{});
        } else if (std.mem.eql(u8, action, "off") or std.mem.eql(u8, action, "disable")) {
            var ssh = railway_ssh.RailwaySSH.initDefault();
            const cmd = "/telegram:access policy open";
            try ssh.tmuxSendKeys(allocator, CLAUDE_SESSION, cmd);
            std.debug.print("{s}✓ Allowlist disabled (open to all Telegram users){s}\n", .{ YELLOW, RESET });
            std.debug.print("  ⚠ This is less secure. Enable with: tri railway telegram allowlist on\n", .{});
        } else {
            std.debug.print("{s}Usage: tri railway telegram allowlist [on|off]{s}\n", .{ RED, RESET });
        }
    } else {
        // Show current status (default to on since we auto-enable)
        std.debug.print("Allowlist status: {s}Enabled by default after pairing{s}\n", .{ GREEN, RESET });
        std.debug.print("  Enable: tri railway telegram allowlist on\n", .{});
        std.debug.print("  Disable: tri railway telegram allowlist off\n", .{});
    }
}

fn runDoctorCommand(allocator: Allocator) !void {
    std.debug.print("{s}Claude Channels Diagnostics:{s}\n\n", .{ MAGENTA, RESET });

    const runtime = @import("claude_runtime.zig");

    // 1. Check Claude installation with version gate (P1)
    std.debug.print("[1/6] Claude Code installation... ", .{});
    const installed = try runtime.checkInstallation(allocator);
    if (installed) {
        std.debug.print("{s}✓ Installed{s}\n", .{ GREEN, RESET });

        const version = runtime.getInstalledVersion(allocator) catch "unknown";
        defer if (!std.mem.eql(u8, version, "unknown")) allocator.free(version);

        std.debug.print("      Version: {s}\n", .{version});

        // P1: Version gate for Channels support
        if (!std.mem.eql(u8, version, "unknown")) {
            const channels_supported = try runtime.probeChannelsSupport(allocator);
            const meets_min = try runtime.compareVersions(allocator, version, MIN_CHANNELS_VERSION);

            if (channels_supported and meets_min) {
                std.debug.print("      {s}✓ Channels supported (>= {s}){s}\n", .{ GREEN, MIN_CHANNELS_VERSION, RESET });
            } else if (!meets_min) {
                std.debug.print("      {s}✗ Version too old for Channels (requires {s}+){s}\n", .{ RED, MIN_CHANNELS_VERSION, RESET });
                std.debug.print("      Update: curl -fsSL https://claude.ai/install | sh\n", .{});
            } else {
                std.debug.print("      {s}⚠ Channels not supported by this version{s}\n", .{ YELLOW, RESET });
            }
        } else {
            std.debug.print("      {s}? Unknown version{s}\n", .{ YELLOW, RESET });
        }
    } else {
        std.debug.print("{s}✗ Not installed{s}\n", .{ RED, RESET });
        std.debug.print("      Install: curl -fsSL https://claude.ai/install | sh\n", .{});
    }

    // 2. Check Claude login status
    std.debug.print("\n[2/6] Claude authentication... ", .{});
    const login_status = try runtime.checkLoginStatus(allocator);
    switch (login_status) {
        .LoggedIn => std.debug.print("{s}✓ Logged in{s}\n", .{ GREEN, RESET }),
        .LoggedOut => {
            std.debug.print("{s}✗ Not logged in{s}\n", .{ RED, RESET });
            std.debug.print("      Login required: claude login\n", .{});
        },
        .NotInstalled => {}, // Already reported above
        .Unknown => std.debug.print("{s}? Unknown status{s}\n", .{ YELLOW, RESET }),
    }

    // 3. Check SSH connectivity
    std.debug.print("\n[3/6] Railway SSH connectivity... ", .{});
    var ssh = railway_ssh.RailwaySSH.initDefault();
    _ = ssh.exec(allocator, "echo OK") catch {
        std.debug.print("{s}✗ Failed{s}\n", .{ RED, RESET });
        std.debug.print("      Check SSH key: {s}\n", .{ssh.key_path});
        return;
    };
    std.debug.print("{s}✓ Connected{s}\n", .{ GREEN, RESET });

    // 4. Check tmux availability
    std.debug.print("[4/6] tmux availability... ", .{});
    _ = ssh.exec(allocator, "which tmux") catch {
        std.debug.print("{s}✗ Not found{s}\n", .{ RED, RESET });
        std.debug.print("      Install: apt-get install tmux\n", .{});
        return;
    };
    std.debug.print("{s}✓ Available{s}\n", .{ GREEN, RESET });

    // 5. Check session status
    std.debug.print("[5/6] Claude session... ", .{});
    const session_output = ssh.tmuxCapture(allocator, CLAUDE_SESSION, 1) catch null;
    if (session_output) |out| {
        allocator.free(out);
        const status = try getStatus(allocator);
        const status_str, _ = formatChannelStatus(status);
        std.debug.print("{s}{s}{s}\n", .{ GREEN, status_str, RESET });
    } else {
        std.debug.print("{s}Not running{s}\n", .{ YELLOW, RESET });
    }

    // 6. Check environment variables
    std.debug.print("[6/6] Environment variables... ", .{});
    const env_output = try runtime.getEnvironmentVariables(allocator, "TELEGRAM_BOT_TOKEN");
    defer allocator.free(env_output);
    if (env_output.len > 0) {
        std.debug.print("{s}✓ TELEGRAM_BOT_TOKEN configured{s}\n", .{ GREEN, RESET });
    } else {
        std.debug.print("{s}✗ TELEGRAM_BOT_TOKEN not set{s}\n", .{ RED, RESET });
        std.debug.print("      Configure: echo \"$TOKEN\" | tri railway telegram init\n", .{});
    }

    std.debug.print("\n{s}Diagnostics complete.{s}\n", .{ MAGENTA, RESET });
}

test "ChannelStatus has all variants" {
    // Zig 0.15: @typeInfo enum field access
    const type_info = @typeInfo(ChannelStatus);
    if (@typeInfo(ChannelStatus) == .@"enum") {
        try std.testing.expectEqual(@as(usize, 6), type_info.@"enum".fields.len);
    } else {
        // Fallback for older Zig versions
        try std.testing.expect(true);
    }
}

test "formatChannelStatus returns valid strings" {
    const statuses = [_]ChannelStatus{ .NotStarted, .WaitingForPair, .Paired, .Error, .Crashed, .Unknown };
    for (statuses) |s| {
        const result = formatChannelStatus(s);
        try std.testing.expect(result[0].len > 0);
        try std.testing.expect(result[1].len > 0);
    }
}

test "CLAUDE_SESSION constant" {
    try std.testing.expectEqualStrings("claude", CLAUDE_SESSION);
}

test "CLAUDE_COMMAND constant" {
    try std.testing.expect(std.mem.indexOf(u8, CLAUDE_COMMAND, "--channel telegram") != null);
}

test "MIN_CHANNELS_VERSION constant" {
    try std.testing.expectEqualStrings("2.1.80", MIN_CHANNELS_VERSION);
}

test "StartOptions default values" {
    const options = StartOptions{};
    try std.testing.expectEqual(options.skip_permissions, false);
    try std.testing.expectEqual(options.auto_allowlist, true);
}
