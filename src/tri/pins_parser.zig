// @origin(spec:pins_parser.tri) @regen(manual-impl)
//
// Trinity Pins DSL Parser & Code Generator
// Single source of truth for FPGA pin mapping → XDC/PCF/JSON backends
//
// Architecture:
//   .tri files → Lexer → Parser → AST → IR → Validator → Emitters (XDC/PCF/JSON)
//
// phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");

// =============================================================================
// LEXER
// =============================================================================

pub const Token = struct {
    type: TokenType,
    lexeme: []const u8,
    line: u32,
    col: u32,
};

pub const TokenType = enum {
    // Keywords
    kw_fpga,
    kw_board,
    kw_design,
    kw_uses,
    kw_on,
    kw_to,
    kw_bind,
    kw_pin,
    kw_clock,
    kw_uart,
    kw_led,
    kw_connector,
    kw_net,
    kw_bank,
    kw_io,
    kw_role,
    kw_freq,
    kw_baud,
    kw_polarity,
    kw_color,
    kw_gnd,
    kw_vcc_5v,
    kw_cts,
    kw_rts,
    kw_txd,
    kw_rxd,

    // Identifiers and literals
    identifier,
    string_literal,

    // Punctuation
    lbrace,
    rbrace,
    lparen,
    rparen,
    dot,
    semicolon,
    comma,

    // Operators
    eq,

    // Special
    eof,
    illegal,
};

pub const Lexer = struct {
    source: []const u8,
    pos: usize = 0,
    line: u32 = 1,
    col: u32 = 1,

    const keywords = std.StaticStringMap(TokenType).initComptime(.{
        .{ "fpga", .kw_fpga },
        .{ "board", .kw_board },
        .{ "design", .kw_design },
        .{ "uses", .kw_uses },
        .{ "on", .kw_on },
        .{ "to", .kw_to },
        .{ "bind", .kw_bind },
        .{ "pin", .kw_pin },
        .{ "clock", .kw_clock },
        .{ "uart", .kw_uart },
        .{ "led", .kw_led },
        .{ "connector", .kw_connector },
        .{ "net", .kw_net },
        .{ "bank", .kw_bank },
        .{ "io", .kw_io },
        .{ "role", .kw_role },
        .{ "freq", .kw_freq },
        .{ "baud", .kw_baud },
        .{ "polarity", .kw_polarity },
        .{ "color", .kw_color },
        .{ "gnd", .kw_gnd },
        .{ "vcc_5v", .kw_vcc_5v },
        .{ "cts", .kw_cts },
        .{ "rts", .kw_rts },
        .{ "txd", .kw_txd },
        .{ "rxd", .kw_rxd },
    });

    pub fn init(source: []const u8) Lexer {
        return .{ .source = source };
    }

    pub fn nextToken(self: *Lexer) Token {
        self.skipWhitespace();

        if (self.pos >= self.source.len) {
            return .{
                .type = .eof,
                .lexeme = "",
                .line = self.line,
                .col = self.col,
            };
        }

        const start_line = self.line;
        const start_col = self.col;
        const start = self.pos;

        const c = self.source[self.pos];
        self.pos += 1;
        self.col += 1;

        return switch (c) {
            '{' => self.token(.lbrace, start, start_line, start_col),
            '}' => self.token(.rbrace, start, start_line, start_col),
            '(' => self.token(.lparen, start, start_line, start_col),
            ')' => self.token(.rparen, start, start_line, start_col),
            '.' => self.token(.dot, start, start_line, start_col),
            ';' => self.token(.semicolon, start, start_line, start_col),
            ',' => self.token(.comma, start, start_line, start_col),
            '=' => self.token(.eq, start, start_line, start_col),
            '#' => {
                // Line comment
                while (self.pos < self.source.len and self.source[self.pos] != '\n') {
                    self.pos += 1;
                }
                return self.nextToken();
            },
            '"', '\'' => {
                // String literal
                while (self.pos < self.source.len and self.source[self.pos] != c) {
                    if (self.source[self.pos] == '\n') {
                        self.line += 1;
                        self.col = 0;
                    }
                    self.pos += 1;
                    self.col += 1;
                }
                if (self.pos < self.source.len) {
                    self.pos += 1; // closing quote
                    self.col += 1;
                }
                return .{
                    .type = .string_literal,
                    .lexeme = self.source[start..self.pos],
                    .line = start_line,
                    .col = start_col,
                };
            },
            'a'...'z', 'A'...'Z', '_' => {
                // Identifier or keyword
                while (self.pos < self.source.len and (std.ascii.isAlphanumeric(self.source[self.pos]) or self.source[self.pos] == '_')) {
                    self.pos += 1;
                    self.col += 1;
                }
                const lexeme = self.source[start..self.pos];
                const token_type = keywords.get(lexeme) orelse .identifier;
                return .{
                    .type = token_type,
                    .lexeme = lexeme,
                    .line = start_line,
                    .col = start_col,
                };
            },
            '0'...'9' => {
                // Number (may include suffix like Hz, MHz, kHz)
                while (self.pos < self.source.len and (std.ascii.isDigit(self.source[self.pos]) or
                    self.source[self.pos] == '.' or std.ascii.isAlphabetic(self.source[self.pos]))) {
                    self.pos += 1;
                    self.col += 1;
                }
                return self.token(.identifier, start, start_line, start_col); // Treat as identifier for now
            },
            else => self.token(.illegal, start, start_line, start_col),
        };
    }

    fn token(self: *Lexer, typ: TokenType, start: usize, line: u32, col: u32) Token {
        return .{
            .type = typ,
            .lexeme = self.source[start..self.pos],
            .line = line,
            .col = col,
        };
    }

    fn skipWhitespace(self: *Lexer) void {
        while (self.pos < self.source.len) {
            const c = self.source[self.pos];
            if (c == ' ' or c == '\t' or c == '\r') {
                self.pos += 1;
                self.col += 1;
            } else if (c == '\n') {
                self.pos += 1;
                self.line += 1;
                self.col = 1;
            } else {
                break;
            }
        }
    }
};

// =============================================================================
// AST
// =============================================================================

pub const Attribute = struct {
    name: []const u8,
    value: []const u8,
};

pub const PinDef = struct {
    name: []const u8,
    loc: ?[]const u8 = null,
    bank: ?u32 = null,
    io: ?[]const u8 = null,
    role: ?[]const u8 = null,
    freq: ?[]const u8 = null,
    polarity: ?[]const u8 = null,
    color: ?[]const u8 = null,
    baud: ?u32 = null,
};

pub const SignalDef = struct {
    name: []const u8,
    signal_type: SignalType,
    pins: std.StringHashMap(PinDef),
    allocator: std.mem.Allocator,
    // Signal-level attributes
    freq: ?[]const u8 = null,
    baud: ?u32 = null,
    polarity: ?[]const u8 = null,
    color: ?[]const u8 = null,

    const SignalType = enum {
        clock,
        uart,
        led,
        connector,
    };

    pub fn init(allocator: std.mem.Allocator, name: []const u8, signal_type: SignalType) SignalDef {
        return .{
            .name = name,
            .signal_type = signal_type,
            .pins = std.StringHashMap(PinDef).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *SignalDef) void {
        var iter = self.pins.iterator();
        while (iter.next()) |entry| {
            _ = entry;
            // PinDef has no deinit - slices point to source memory
        }
        self.pins.deinit();
    }
};

pub const FpgaDecl = struct {
    name: []const u8,
    pins: std.StringHashMap(PinDef),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator, name: []const u8) FpgaDecl {
        return .{
            .name = name,
            .pins = std.StringHashMap(PinDef).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *FpgaDecl) void {
        // PinDef has no deinit - slices point to source memory
        self.pins.deinit();
    }
};

pub const BoardDecl = struct {
    name: []const u8,
    uses_fpga: ?[]const u8 = null,
    clocks: std.StringHashMap(SignalDef),
    uarts: std.StringHashMap(SignalDef),
    leds: std.StringHashMap(SignalDef),
    connectors: std.StringHashMap(SignalDef),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator, name: []const u8) BoardDecl {
        return .{
            .name = name,
            .clocks = std.StringHashMap(SignalDef).init(allocator),
            .uarts = std.StringHashMap(SignalDef).init(allocator),
            .leds = std.StringHashMap(SignalDef).init(allocator),
            .connectors = std.StringHashMap(SignalDef).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *BoardDecl) void {
        var iter = self.clocks.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        self.clocks.deinit();

        iter = self.uarts.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        self.uarts.deinit();

        iter = self.leds.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        self.leds.deinit();

        iter = self.connectors.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        self.connectors.deinit();
    }

    pub fn constDeinit(self: *const BoardDecl) void {
        var mutable = @constCast(self);
        var iter = mutable.clocks.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        mutable.clocks.deinit();

        iter = mutable.uarts.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        mutable.uarts.deinit();

        iter = mutable.leds.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        mutable.leds.deinit();

        iter = mutable.connectors.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit();
        }
        mutable.connectors.deinit();
    }
};

pub const Binding = struct {
    port: []const u8,
    target: []const u8, // e.g., "board.clock.osc50"
};

pub const DesignDecl = struct {
    name: []const u8,
    target_board: ?[]const u8 = null,
    bindings: std.ArrayList(Binding),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator, name: []const u8) DesignDecl {
        const bindings = std.ArrayList(Binding).initCapacity(allocator, 0) catch unreachable;
        const design: DesignDecl = .{
            .name = name,
            .bindings = bindings,
            .allocator = allocator,
        };
        return design;
    }

    pub fn deinit(self: *DesignDecl) void {
        self.bindings.deinit(self.allocator);
    }

    pub fn constDeinit(self: *const DesignDecl) void {
        // Cast away const for deinit (safe because we own the data)
        @constCast(self).bindings.deinit(self.allocator);
    }
};

// =============================================================================
// PARSER
// =============================================================================

pub const ParseError = error{
    UnexpectedToken,
    ExpectedIdentifier,
    ExpectedLbrace,
    ExpectedRbrace,
    ExpectedUses,
    ExpectedOn,
    ExpectedTo,
    ExpectedBind,
    DuplicateDefinition,
    InvalidSyntax,
    OutOfMemory,
};

pub const Parser = struct {
    lexer: Lexer,
    current: Token,
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator, source: []const u8) Parser {
        var lexer = Lexer.init(source);
        const current = lexer.nextToken();
        return .{
            .lexer = lexer,
            .current = current,
            .allocator = allocator,
        };
    }

    fn advance(self: *Parser) Token {
        const prev = self.current;
        self.current = self.lexer.nextToken();
        return prev;
    }

    fn check(self: *const Parser, typ: TokenType) bool {
        return self.current.type == typ;
    }

    fn consume(self: *Parser, typ: TokenType) !Token {
        if (self.check(typ)) {
            return self.advance();
        }
        std.debug.print("Line {d}: Expected {s}, got {s}\n", .{
            self.current.line,
            @tagName(typ),
            @tagName(self.current.type),
        });
        return ParseError.UnexpectedToken;
    }

    fn consumeIdentifier(self: *Parser) ![]const u8 {
        // Accept both identifiers and keywords as identifiers (port names can be keywords)
        if (self.check(.identifier) or self.isKeyword()) {
            return self.advance().lexeme;
        }
        std.debug.print("consumeIdentifier error: current={s} type={s}\n", .{
            self.current.lexeme, @tagName(self.current.type),
        });
        return ParseError.ExpectedIdentifier;
    }

    fn isKeyword(self: *const Parser) bool {
        return self.check(.kw_fpga) or self.check(.kw_board) or self.check(.kw_design) or
            self.check(.kw_uses) or self.check(.kw_on) or self.check(.kw_to) or self.check(.kw_bind) or
            self.check(.kw_pin) or self.check(.kw_clock) or self.check(.kw_uart) or self.check(.kw_led) or
            self.check(.kw_connector) or self.check(.kw_net) or self.check(.kw_bank) or self.check(.kw_io) or
            self.check(.kw_role) or self.check(.kw_freq) or self.check(.kw_baud) or self.check(.kw_polarity) or
            self.check(.kw_color) or self.check(.kw_gnd) or self.check(.kw_vcc_5v) or self.check(.kw_cts) or
            self.check(.kw_rts) or self.check(.kw_txd) or self.check(.kw_rxd);
    }

    fn consumePath(self: *Parser) ![]const u8 {
        // Paths are like: board.clock.osc50 or board.uart.ft232rl.txd
        // They can contain dots, and components can be keywords (board, clock, uart, led, etc.)
        var path_parts = std.ArrayList([]const u8).initCapacity(self.allocator, 4) catch unreachable;
        defer path_parts.deinit(self.allocator);

        // Accept identifier or keyword as path component
        const isPathComponent = self.check(.identifier) or self.check(.kw_fpga) or
            self.check(.kw_board) or self.check(.kw_clock) or self.check(.kw_uart) or
            self.check(.kw_led) or self.check(.kw_connector);

        if (!isPathComponent) {
            std.debug.print("Expected path component, got: {s} ({s})\n", .{
                self.current.lexeme, @tagName(self.current.type),
            });
            return ParseError.ExpectedIdentifier;
        }

        try path_parts.append(self.allocator, self.advance().lexeme);

        // Check for more parts connected by dots
        while (self.check(.dot)) {
            _ = self.advance(); // consume dot
            const nextIsPathComponent = self.check(.identifier) or self.check(.kw_fpga) or
                self.check(.kw_board) or self.check(.kw_clock) or self.check(.kw_uart) or
                self.check(.kw_led) or self.check(.kw_connector) or self.check(.kw_txd) or
                self.check(.kw_rxd) or self.check(.kw_net) or self.check(.kw_gnd);

            if (!nextIsPathComponent) {
                std.debug.print("Expected path component after dot, got: {s} ({s})\n", .{
                    self.current.lexeme, @tagName(self.current.type),
                });
                return ParseError.ExpectedIdentifier;
            }

            try path_parts.append(self.allocator, self.advance().lexeme);
        }

        // Join all parts with dots
        const full_path = std.mem.join(self.allocator, ".", path_parts.items) catch {
            return ParseError.OutOfMemory;
        };
        return full_path;
    }

    pub fn parseFpgaDecl(self: *Parser) !FpgaDecl {
        _ = try self.consume(.kw_fpga);
        const name = try self.consumeIdentifier();
        _ = try self.consume(.lbrace);

        var fpga = FpgaDecl.init(self.allocator, name);
        errdefer fpga.deinit();

        while (!self.check(.rbrace) and !self.check(.eof)) {
            if (self.check(.kw_pin)) {
                _ = try self.consume(.kw_pin);
                const pin_name = try self.consumeIdentifier();
                _ = try self.consume(.lbrace);

                var pin = PinDef{
                    .name = pin_name,
                };

                // Parse pin attributes
                while (!self.check(.rbrace) and !self.check(.eof)) {
                    const attr_name = try self.consumeIdentifier();

                    if (std.mem.eql(u8, attr_name, "bank")) {
                        const bank_str = try self.consumeIdentifier();
                        pin.bank = std.fmt.parseInt(u32, bank_str, 10) catch 0;
                    } else if (std.mem.eql(u8, attr_name, "io")) {
                        pin.io = try self.consumeIdentifier();
                    } else if (std.mem.eql(u8, attr_name, "role")) {
                        pin.role = try self.consumeIdentifier();
                    } else {
                        _ = try self.consumeIdentifier(); // skip value
                    }
                    // Consume optional semicolon
                    if (self.check(.semicolon)) {
                        _ = self.advance();
                    }
                }

                _ = try self.consume(.rbrace);
                try fpga.pins.put(pin_name, pin);
            } else {
                std.mem.doNotOptimizeAway(self.advance());
            }
        }

        _ = try self.consume(.rbrace);
        return fpga;
    }

    pub fn parseBoardDecl(self: *Parser) !BoardDecl {
        _ = try self.consume(.kw_board);
        const name = try self.consumeIdentifier();
        _ = try self.consume(.lbrace);

        var board = BoardDecl.init(self.allocator, name);
        errdefer board.deinit();

        while (!self.check(.rbrace) and !self.check(.eof)) {
            if (self.check(.kw_uses)) {
                _ = try self.consume(.kw_uses);
                board.uses_fpga = try self.consumeIdentifier();
            } else if (self.check(.kw_clock)) {
                _ = try self.consume(.kw_clock);
                const clock_name = try self.consumeIdentifier();
                _ = try self.consume(.lbrace);

                var clock = SignalDef.init(self.allocator, clock_name, .clock);
                try self.parseSignalAttributes(&clock);

                try board.clocks.put(clock_name, clock);
                _ = try self.consume(.rbrace);
            } else if (self.check(.kw_uart)) {
                _ = try self.consume(.kw_uart);
                const uart_name = try self.consumeIdentifier();
                _ = try self.consume(.lbrace);

                var uart = SignalDef.init(self.allocator, uart_name, .uart);
                try self.parseSignalAttributes(&uart);

                try board.uarts.put(uart_name, uart);
                _ = try self.consume(.rbrace);
            } else if (self.check(.kw_led)) {
                _ = try self.consume(.kw_led);
                const led_name = try self.consumeIdentifier();
                _ = try self.consume(.lbrace);

                var led = SignalDef.init(self.allocator, led_name, .led);
                try self.parseSignalAttributes(&led);

                try board.leds.put(led_name, led);
                _ = try self.consume(.rbrace);
            } else if (self.check(.kw_connector)) {
                _ = try self.consume(.kw_connector);
                const conn_name = try self.consumeIdentifier();
                _ = try self.consume(.lbrace);

                var conn = SignalDef.init(self.allocator, conn_name, .connector);
                try self.parseConnectorPins(&conn);

                try board.connectors.put(conn_name, conn);
                _ = try self.consume(.rbrace);
            } else {
                std.mem.doNotOptimizeAway(self.advance());
            }
        }

        _ = try self.consume(.rbrace);
        return board;
    }

    fn parseSignalAttributes(self: *Parser, signal: *SignalDef) !void {
        while (!self.check(.rbrace) and !self.check(.eof)) {
            std.debug.print("  parseSignalAttributes: current={s} type={s}\n", .{
                self.current.lexeme, @tagName(self.current.type),
            });
            const attr_name = try self.consumeIdentifier();

            if (std.mem.eql(u8, attr_name, "net")) {
                const net_path = try self.consumePath();
                var pin = PinDef{
                    .name = attr_name,
                };
                // Parse fpga.PIN format
                if (std.mem.indexOf(u8, net_path, ".")) |idx| {
                    _ = idx; // dot position
                    var parts = std.mem.splitScalar(u8, net_path, '.');
                    const fpga_part = parts.first();
                    _ = fpga_part; // fpga
                    const pin_part = parts.rest();
                    pin.loc = pin_part;
                } else {
                    pin.loc = net_path;
                }
                try signal.pins.put(attr_name, pin);
            } else if (std.mem.eql(u8, attr_name, "txd") or std.mem.eql(u8, attr_name, "rxd") or
                std.mem.eql(u8, attr_name, "gnd"))
            {
                const value = try self.consumePath(); // J2.6 is a path
                const pin = PinDef{
                    .name = attr_name,
                    .loc = value,
                };
                try signal.pins.put(attr_name, pin);
            } else if (std.mem.eql(u8, attr_name, "freq")) {
                signal.freq = try self.consumeIdentifier();
            } else if (std.mem.eql(u8, attr_name, "baud")) {
                const baud_str = try self.consumeIdentifier();
                signal.baud = std.fmt.parseInt(u32, baud_str, 10) catch 115200;
            } else if (std.mem.eql(u8, attr_name, "polarity")) {
                signal.polarity = try self.consumeIdentifier();
            } else if (std.mem.eql(u8, attr_name, "color")) {
                signal.color = try self.consumeIdentifier();
            } else {
                _ = try self.consumeIdentifier(); // skip value
            }
        }
    }

    fn parseConnectorPins(self: *Parser, conn: *SignalDef) !void {
        // Format: pin <number> <signal_name>
        // Example: pin 1 gnd
        while (!self.check(.rbrace) and !self.check(.eof)) {
            if (self.check(.kw_pin)) {
                _ = try self.consume(.kw_pin);
                // Pin number (may be numeric identifier)
                const pin_num_str = try self.consumeIdentifier();
                // Signal name (may be keyword like gnd, vcc_5v, etc.)
                const signal_name = try self.consumeIdentifier();

                const pin = PinDef{
                    .name = pin_num_str,
                    .loc = signal_name, // Signal name is the "location" (what it connects to)
                };
                try conn.pins.put(pin_num_str, pin);
            } else {
                // Skip unknown tokens
                _ = self.advance();
            }
        }
    }

    pub fn parseDesignDecl(self: *Parser) !DesignDecl {
        _ = try self.consume(.kw_design);
        const name = try self.consumeIdentifier();

        if (self.check(.kw_on)) {
            _ = try self.consume(.kw_on);
            // target board name
        }
        const target_board = try self.consumeIdentifier();

        _ = try self.consume(.lbrace);

        var design = DesignDecl.init(self.allocator, name);
        design.target_board = target_board;
        errdefer design.deinit();

        while (!self.check(.rbrace) and !self.check(.eof)) {
            if (self.check(.kw_bind)) {
                _ = try self.consume(.kw_bind);
                const port = try self.consumeIdentifier();
                _ = try self.consume(.kw_to);
                const target = try self.consumePath();

                try design.bindings.append(self.allocator, .{
                    .port = port,
                    .target = target,
                });
            } else {
                std.mem.doNotOptimizeAway(self.advance());
            }
        }

        _ = try self.consume(.rbrace);
        return design;
    }
};

// =============================================================================
// VALIDATOR
// =============================================================================

pub const ValidationError = struct {
    message: []const u8,
    line: u32,
    col: u32,
};

pub const Validator = struct {
    errors: std.ArrayList(ValidationError),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) Validator {
        const errors = std.ArrayList(ValidationError).initCapacity(allocator, 0) catch unreachable;
        const validator: Validator = .{
            .errors = errors,
            .allocator = allocator,
        };
        return validator;
    }

    pub fn deinit(self: *Validator) void {
        self.errors.deinit(self.allocator);
    }

    pub fn hasErrors(self: *const Validator) bool {
        return self.errors.items.len > 0;
    }

    pub fn report(self: *const Validator) void {
        for (self.errors.items) |err| {
            std.debug.print("  {s}Line {d}:{d}: {s}{s}\n", .{
                "\x1b[31m", err.line, err.col, err.message, "\x1b[0m",
            });
        }
    }

    pub fn validateFpga(self: *Validator, fpga: *const FpgaDecl) !void {
        // Check for duplicate pin locations
        var seen_locs = std.StringHashMap(void).init(self.allocator);
        defer seen_locs.deinit();

        var iter = fpga.pins.iterator();
        while (iter.next()) |entry| {
            const pin = entry.value_ptr.*;
            if (pin.loc) |loc| {
                if (seen_locs.get(loc) != null) {
                    try self.errors.append(self.allocator, .{
                        .message = try std.fmt.allocPrint(
                            self.allocator,
                            "Duplicate pin location '{s}' for pin '{s}'",
                            .{ loc, pin.name },
                        ),
                        .line = 0,
                        .col = 0,
                    });
                }
                try seen_locs.put(loc, {});
            }
        }
    }

    pub fn validateBoard(self: *Validator, board: *const BoardDecl) !void {
        if (board.uses_fpga == null) {
            try self.errors.append(self.allocator, .{
                .message = "Board must specify 'uses <fpga>'",
                .line = 0,
                .col = 0,
            });
        }
    }

    pub fn validateDesign(self: *Validator, design: *const DesignDecl, _: *const BoardDecl) !void {
        if (design.target_board == null) {
            try self.errors.append(self.allocator, .{
                .message = "Design must specify target board",
                .line = 0,
                .col = 0,
            });
            return;
        }

        // Check that all bindings resolve to board signals
        for (design.bindings.items) |binding| {
            // Simple check: does target exist in board?
            // For now, just check the format
            const has_board_prefix = std.mem.indexOf(u8, binding.target, "board.") != null;
            const has_dot = std.mem.indexOf(u8, binding.target, ".") != null;
            if (!has_board_prefix and has_dot) {
                try self.errors.append(self.allocator, .{
                    .message = try std.fmt.allocPrint(
                        self.allocator,
                        "Invalid binding target '{s}' for port '{s}'",
                        .{ binding.target, binding.port },
                    ),
                    .line = 0,
                    .col = 0,
                });
            }
        }
    }
};

// =============================================================================
// XDC EMITTER
// =============================================================================

pub const XdcEmitter = struct {
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) XdcEmitter {
        return .{ .allocator = allocator };
    }

    pub fn generateXdc(
        self: *const XdcEmitter,
        design: *const DesignDecl,
        board: *const BoardDecl,
        fpga: *const FpgaDecl,
    ) ![]const u8 {
        var buffer = std.ArrayList(u8).initCapacity(self.allocator, 1024) catch unreachable;
        errdefer buffer.deinit(self.allocator);

        const writer = buffer.writer(self.allocator);

        // Debug: check string pointers before print
        std.debug.print("DEBUG: design.name={*} len={d}\n", .{ design.name.ptr, design.name.len });
        std.debug.print("DEBUG: board.name={*} len={d}\n", .{ board.name.ptr, board.name.len });
        std.debug.print("DEBUG: fpga.name={*} len={d}\n", .{ fpga.name.ptr, fpga.name.len });

        // Header
        try writer.print(
            \\# ============================================================================
            \\# XDC Constraints generated from Trinity Pins DSL
            \\# Design: {s}
            \\# Board: {s}
            \\# FPGA: {s}
            \\# ============================================================================
            \\
        , .{ design.name, board.name, fpga.name });

        // Track used locations for duplicate detection
        var used_locs = std.StringHashMap(void).init(self.allocator);
        defer used_locs.deinit();

        // Process bindings
        for (design.bindings.items) |binding| {
            // Parse target path: board.clock.osc50 -> find signal osc50 in clocks
            var path_parts = std.mem.splitScalar(u8, binding.target, '.');
            var part_idx: usize = 0;
            var signal_type: []const u8 = undefined;
            var signal_name: []const u8 = undefined;
            var pin_attr: []const u8 = "net"; // default attribute

            while (path_parts.next()) |part| {
                if (part_idx == 1) signal_type = part;
                if (part_idx == 2) signal_name = part;
                if (part_idx == 3) pin_attr = part;
                part_idx += 1;
            }

            // Find the signal
            const loc = blk: {
                if (std.mem.eql(u8, signal_type, "clock")) {
                    if (board.clocks.get(signal_name)) |sig| {
                        if (sig.pins.get(pin_attr)) |pin| break :blk pin.loc;
                    }
                } else if (std.mem.eql(u8, signal_type, "uart")) {
                    if (board.uarts.get(signal_name)) |sig| {
                        if (std.mem.eql(u8, binding.port, "uart_rx")) {
                            if (sig.pins.get("txd")) |pin| break :blk pin.loc;
                        } else if (std.mem.eql(u8, binding.port, "uart_tx")) {
                            if (sig.pins.get("rxd")) |pin| break :blk pin.loc;
                        }
                    }
                } else if (std.mem.eql(u8, signal_type, "led")) {
                    if (board.leds.get(signal_name)) |sig| {
                        if (sig.pins.get("net")) |pin| break :blk pin.loc;
                    }
                }
                continue;
            };

            if (loc) |pin_loc| {
                // Check for duplicates
                if (used_locs.get(pin_loc) != null) {
                    std.debug.print("Warning: duplicate location {s} for port {s}\n", .{ pin_loc, binding.port });
                }
                try used_locs.put(pin_loc, {});

                // Get IO standard from FPGA definition
                const io_standard = blk: {
                    if (fpga.pins.get(pin_loc)) |pin| {
                        if (pin.io) |io| break :blk io;
                    }
                    break :blk "LVCMOS33";
                };

                // Emit XDC constraint
                try writer.print("# {s}\n", .{binding.target});
                try writer.print("set_property LOC {s} [get_ports {s}]\n", .{ pin_loc, binding.port });
                try writer.print("set_property IOSTANDARD {s} [get_ports {s}]\n", .{ io_standard, binding.port });
                try writer.writeAll("\n");
            }
        }

        // Bitstream config
        try writer.writeAll(
            \\# Bitstream config
            \\set_property CFGBVS VCCO [current_design]
            \\set_property CONFIG_VOLTAGE 3.3 [current_design]
            \\
        );

        return buffer.toOwnedSlice(self.allocator);
    }
};

// =============================================================================
// SIMPLE PARSE WRAPPER
// =============================================================================

pub fn parseDesignFile(allocator: std.mem.Allocator, path: []const u8) !struct {
    design: DesignDecl,
    board: BoardDecl,
    fpga: FpgaDecl,
} {
    const content = std.fs.cwd().readFileAlloc(allocator, path, 1024 * 1024) catch |err| {
        std.debug.print("Failed to read {s}: {}\n", .{ path, err });
        return error.FileNotFound;
    };
    defer allocator.free(content);

    var parser = Parser.init(allocator, content);
    var design = try parser.parseDesignDecl();
    errdefer design.deinit();

    // Get base path (directory containing designs/ folder)
    const base_path = if (std.mem.indexOf(u8, path, "/designs/")) |idx|
        path[0..idx]
    else
        "";

    // Load board file
    const board_path = if (base_path.len > 0)
        try std.fmt.allocPrint(allocator, "{s}/boards/{s}.board.tri", .{
            base_path,
            design.target_board.?,
        })
    else
        "fpga/boards/qmtech_xc7a100t.board.tri";

    const board_content = std.fs.cwd().readFileAlloc(allocator, board_path, 1024 * 1024) catch |err| {
        std.debug.print("Failed to read {s}: {}\n", .{ board_path, err });
        return error.FileNotFound;
    };
    defer allocator.free(board_content);
    if (base_path.len > 0) allocator.free(board_path);

    var board_parser = Parser.init(allocator, board_content);
    var board = try board_parser.parseBoardDecl();
    errdefer board.deinit();

    // Load FPGA file
    const fpga_path = if (base_path.len > 0 and board.uses_fpga != null)
        try std.fmt.allocPrint(allocator, "{s}/fabric/{s}.fabric.tri", .{
            base_path,
            board.uses_fpga.?,
        })
    else
        "fpga/fabric/xc7a100t_fgg676.fabric.tri";

    const fpga_content = std.fs.cwd().readFileAlloc(allocator, fpga_path, 1024 * 1024) catch |err| {
        std.debug.print("Failed to read {s}: {}\n", .{ fpga_path, err });
        return error.FileNotFound;
    };
    defer allocator.free(fpga_content);
    if (base_path.len > 0 and board.uses_fpga != null) allocator.free(fpga_path);

    var fpga_parser = Parser.init(allocator, fpga_content);
    const fpga = try fpga_parser.parseFpgaDecl();

    return .{
        .design = design,
        .board = board,
        .fpga = fpga,
    };
}

// =============================================================================
// HIGH-LEVEL API FUNCTIONS
// =============================================================================

/// Validation result
pub const ValidationResult = struct {
    valid: bool,
    bindings_count: usize,
    warnings_count: usize,
    errors: std.ArrayList([]const u8),

    pub fn deinit(self: *ValidationResult, allocator: std.mem.Allocator) void {
        for (self.errors.items) |err| {
            allocator.free(err);
        }
        self.errors.deinit(allocator);
    }
};

/// Generate XDC from design file
pub fn generateXdcFromDesign(allocator: std.mem.Allocator, design_path: []const u8) ![]const u8 {
    const result = try parseDesignFile(allocator, design_path);
    defer {
        result.design.constDeinit();
        result.board.constDeinit();
    }

    var emitter = XdcEmitter.init(allocator);
    return emitter.generateXdc(&result.design, &result.board, &result.fpga);
}

/// Validate design file
pub fn validateDesign(allocator: std.mem.Allocator, design_path: []const u8) !ValidationResult {
    const result = try parseDesignFile(allocator, design_path);
    defer {
        result.design.constDeinit();
        result.board.constDeinit();
    }

    var ret = ValidationResult{
        .valid = true,
        .bindings_count = result.design.bindings.items.len,
        .warnings_count = 0,
        .errors = std.ArrayList([]const u8).initCapacity(allocator, 0) catch unreachable,
    };

    // Validate each binding
    var validator = Validator.init(allocator);
    defer validator.deinit();

    try validator.validateDesign(&result.design, &result.board, &result.fpga);

    if (validator.hasErrors()) {
        ret.valid = false;
        try ret.errors.ensureUnusedCapacity(validator.errors.items.len);
        for (validator.errors.items) |err| {
            const msg = try std.fmt.allocPrint(allocator, "Line {d}:{d}: {s}", .{ err.line, err.col, err.message });
            try ret.errors.append(allocator, msg);
        }
    }

    return ret;
}

/// Export intermediate representation as JSON
pub fn exportIr(allocator: std.mem.Allocator, design_path: []const u8) ![]const u8 {
    const result = try parseDesignFile(allocator, design_path);
    defer {
        result.design.constDeinit();
        result.board.constDeinit();
    }

    // Build JSON representation
    var json = std.ArrayList(u8).initCapacity(allocator, 512) catch unreachable;
    errdefer json.deinit(allocator);
    const writer = json.writer(allocator);

    try writer.writeAll("{\n"); // prints {
    try writer.print("  \"design\": \"{s}\",\n", .{result.design.name});
    try writer.print("  \"board\": \"{s}\",\n", .{result.board.name});
    try writer.print("  \"fpga\": \"{s}\",\n", .{result.fpga.name});
    try writer.writeAll("  \"bindings\": [\n");

    for (result.design.bindings.items, 0..) |binding, i| {
        if (i > 0) try writer.writeAll(",\n");
        try writer.print("    {{ \"port\": \"{s}\", \"signal\": \"{s}\" }}", .{ binding.port, binding.target });
    }

    try writer.writeAll("\n  ]\n}\n"); // prints }\n

    return json.toOwnedSlice(allocator);
}
