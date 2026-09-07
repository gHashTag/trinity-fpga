//! Does the migrated socket path actually carry bytes?
//!
//! 0.16 did not rename `std.net`, it redesigned it. `Server.Connection` no
//! longer exists -- `accept(io)` returns a bare `Stream`, and the peer address
//! the old Connection carried is not returned at all. `Stream` itself has no
//! read or write methods; both go through `.reader(io, buf)` / `.writer(io,
//! buf)` and their `.interface`.
//!
//! That change rewrote 21 handler signatures in chat_server.zig, and not one
//! socket had been opened since. A build proves the types line up. It does not
//! prove a byte reaches the other end, that a short read is distinguished from
//! a closed connection, or that the writer's buffering does not swallow the
//! last chunk -- and the last of those is a real hazard, because the 0.16
//! writer buffers and needs an explicit flush.
//!
//! These tests use the same call shapes the handlers do, on a loopback socket
//! with an ephemeral port, so they need no network and cannot collide with a
//! port in use.
//!
//! phi^2 + 1/phi^2 = 3 = TRINITY

const std = @import("std");
const tri_io = @import("tri_io");
const net = std.Io.net;

/// Binds 127.0.0.1 on a kernel-chosen port and reports where it landed.
/// Port 0 rather than a fixed number: a hardcoded port makes the test fail
/// for an unrelated reason on a machine that already uses it.
fn listenLoopback(io: std.Io) !net.Server {
    const addr = try net.IpAddress.parse("127.0.0.1", 0);
    return addr.listen(io, .{ .reuse_address = true });
}

const Echo = struct {
    server: *net.Server,
    io: std.Io,
    received: *[64]u8,
    len: *usize,
    ok: *bool,

    /// One accept, read what arrives, write it back. The shape a handler uses.
    fn serve(e: Echo) void {
        var stream = e.server.accept(e.io) catch return;
        defer stream.close(e.io);

        var rbuf: [256]u8 = undefined;
        var r = stream.reader(e.io, &rbuf);
        // fillMore does ONE underlying read. readSliceShort would block here:
        // it loops until the destination is full or the stream ends, and the
        // client is still connected with 36 of 64 bytes sent. That is the read
        // inversion this file exists to pin, and it caught the author first.
        r.interface.fillMore() catch return;
        const got = r.interface.buffered();
        const n = @min(got.len, e.received.len);
        @memcpy(e.received[0..n], got[0..n]);
        e.len.* = n;

        var wbuf: [256]u8 = undefined;
        var w = stream.writer(e.io, &wbuf);
        w.interface.writeAll(e.received[0..n]) catch return;
        // The buffered writer needs this. Without it the bytes sit in the
        // buffer and the client blocks forever -- which is exactly the kind of
        // silent behaviour change a compile cannot catch.
        w.interface.flush() catch return;
        e.ok.* = true;
    }
};

test "a byte written to a migrated socket comes back out of it" {
    const io = tri_io.get();

    var server = try listenLoopback(io);
    defer server.deinit(io);
    const bound = server.socket.address;

    var received: [64]u8 = undefined;
    var received_len: usize = 0;
    var served = false;

    const t = try std.Thread.spawn(.{}, Echo.serve, .{Echo{
        .server = &server,
        .io = io,
        .received = &received,
        .len = &received_len,
        .ok = &served,
    }});

    const payload = "phi squared plus its inverse is three";
    {
        var client = try bound.connect(io, .{ .mode = .stream });
        defer client.close(io);

        var wbuf: [256]u8 = undefined;
        var w = client.writer(io, &wbuf);
        try w.interface.writeAll(payload);
        try w.interface.flush();

        // readSliceAll is right HERE and wrong above: the client knows exactly
        // how many bytes it expects back, so a short read is corruption.
        var rbuf: [256]u8 = undefined;
        var r = client.reader(io, &rbuf);
        var back: [64]u8 = undefined;
        try r.interface.readSliceAll(back[0..payload.len]);

        try std.testing.expectEqualStrings(payload, back[0..payload.len]);
    }
    t.join();

    try std.testing.expect(served);
    try std.testing.expectEqual(payload.len, received_len);
    try std.testing.expectEqualStrings(payload, received[0..received_len]);
}

test "accept yields a Stream, and the listener knows the port it was given" {
    // Pins the two shape changes the handlers had to absorb: accept returns a
    // bare Stream rather than a Connection, and the bound address now comes
    // off the server's socket because accept no longer reports the peer.
    const io = tri_io.get();

    var server = try listenLoopback(io);
    defer server.deinit(io);

    const bound = server.socket.address;
    switch (bound) {
        .ip4 => |v4| try std.testing.expect(v4.port != 0), // the kernel chose one
        .ip6 => |v6| try std.testing.expect(v6.port != 0),
    }

    const Accepted = struct {
        fn run(s: *net.Server, i: std.Io, got: *bool) void {
            var stream = s.accept(i) catch return;
            // The type is the assertion: this is a Stream, not a Connection.
            const T = @TypeOf(stream);
            if (T != net.Stream) return;
            got.* = true;
            stream.close(i);
        }
    };
    var got = false;
    const t = try std.Thread.spawn(.{}, Accepted.run, .{ &server, io, &got });

    var client = try bound.connect(io, .{ .mode = .stream });
    client.close(io);
    t.join();

    try std.testing.expect(got);
}

test "reading a closed connection ends the stream instead of spinning" {
    // The read-path inversion, on a socket. A peer that closes without
    // sending must surface as end-of-stream or a zero-length read -- not as a
    // loop that never terminates, which is what a readAll-shaped translation
    // of this would produce.
    const io = tri_io.get();

    var server = try listenLoopback(io);
    defer server.deinit(io);
    const bound = server.socket.address;

    const Hangup = struct {
        fn run(addr: net.IpAddress, i: std.Io) void {
            var c = addr.connect(i, .{ .mode = .stream }) catch return;
            c.close(i); // connect and immediately go away
        }
    };
    const t = try std.Thread.spawn(.{}, Hangup.run, .{ bound, io });

    var stream = try server.accept(io);
    defer stream.close(io);

    var rbuf: [256]u8 = undefined;
    var r = stream.reader(io, &rbuf);

    // Either answer is correct and both TERMINATE; a hang is the failure this
    // test exists to catch. fillMore returns void, so the outcome is read from
    // the buffer rather than a count.
    if (r.interface.fillMore()) |_| {
        try std.testing.expectEqual(@as(usize, 0), r.interface.buffered().len);
    } else |err| {
        try std.testing.expect(err == error.EndOfStream or err == error.ReadFailed);
    }
    t.join();
}
