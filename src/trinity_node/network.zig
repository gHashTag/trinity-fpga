// ═══════════════════════════════════════════════════════════════════════════════
// TRINITY NODE NETWORK - Main Network Layer
// TCP Job Server + UDP Discovery + Gossip Sync
// V = n × 3^k × π^m × φ^p × e^q
// φ² + 1/φ² = 3 = TRINITY
// ═══════════════════════════════════════════════════════════════════════════════

const std = @import("std");
const tri_io = @import("tri_io");
const tri_mutex = @import("tri_mutex");
const tri_time = @import("tri_time");
const protocol = @import("protocol.zig");
const discovery = @import("discovery.zig");
const wallet_mod = @import("wallet.zig");
const crypto = @import("crypto.zig");

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════════

pub const JOB_PORT: u16 = 9334;
pub const MAX_CONNECTIONS: usize = 64;
pub const MAX_PENDING_JOBS: usize = 256;
pub const JOB_TIMEOUT_MS: u64 = 60000; // 1 minute

// ═══════════════════════════════════════════════════════════════════════════════
// NETWORK STATUS
// ═══════════════════════════════════════════════════════════════════════════════

pub const NetworkStatus = enum {
    disconnected,
    connecting,
    connected,
    syncing,
    ready,
};

// ═══════════════════════════════════════════════════════════════════════════════
// JOB QUEUE
// ═══════════════════════════════════════════════════════════════════════════════

pub const PendingJob = struct {
    job: protocol.InferenceJob,
    received_at: i64,
    // 0.16: std.net is gone; `std.Io.net.IpAddress` is the replacement type.
    client_addr: std.Io.net.IpAddress,
};

pub const JobQueue = struct {
    jobs: [MAX_PENDING_JOBS]?PendingJob,
    head: usize,
    tail: usize,
    count: usize,
    mutex: tri_mutex.Mutex,

    pub fn init() JobQueue {
        return JobQueue{
            .jobs = [_]?PendingJob{null} ** MAX_PENDING_JOBS,
            .head = 0,
            .tail = 0,
            .count = 0,
            .mutex = .{},
        };
    }

    /// Push job to queue
    pub fn push(self: *JobQueue, job: PendingJob) bool {
        self.mutex.lock();
        defer self.mutex.unlock();

        if (self.count >= MAX_PENDING_JOBS) return false;

        self.jobs[self.tail] = job;
        self.tail = (self.tail + 1) % MAX_PENDING_JOBS;
        self.count += 1;
        return true;
    }

    /// Pop job from queue
    pub fn pop(self: *JobQueue) ?PendingJob {
        self.mutex.lock();
        defer self.mutex.unlock();

        if (self.count == 0) return null;

        const job = self.jobs[self.head];
        self.jobs[self.head] = null;
        self.head = (self.head + 1) % MAX_PENDING_JOBS;
        self.count -= 1;
        return job;
    }

    /// Get queue size
    pub fn size(self: *JobQueue) usize {
        self.mutex.lock();
        defer self.mutex.unlock();
        return self.count;
    }
};

// ═══════════════════════════════════════════════════════════════════════════════
// NETWORK NODE
// ═══════════════════════════════════════════════════════════════════════════════

pub const NetworkNode = struct {
    allocator: std.mem.Allocator,
    wallet: *wallet_mod.Wallet,
    discovery_service: *discovery.DiscoveryService,
    job_queue: JobQueue,
    status: NetworkStatus,
    running: std.atomic.Value(bool),
    job_server_thread: ?std.Thread,
    // 0.16: std.posix lost socket/bind/listen/accept entirely, so a bare fd is
    // no longer usable. This now holds the `std.Io.net.Server` that
    // `IpAddress.listen` returns; the name is kept because callers refer to it.
    job_server_socket: ?std.Io.net.Server,
    listen_port: u16,

    // Stats
    jobs_received: u64,
    jobs_completed: u64,
    jobs_failed: u64,
    start_time: i64,

    // Callbacks
    on_job_received: ?*const fn (*NetworkNode, protocol.InferenceJob) void,

    // Storage (optional)
    storage_provider: ?*anyopaque = null,
    storage_peer_registry: ?*anyopaque = null,
    proof_of_storage: ?*anyopaque = null,
    shard_rebalancer: ?*anyopaque = null,
    bandwidth_aggregator: ?*anyopaque = null,
    shard_scrubber: ?*anyopaque = null,
    node_reputation: ?*anyopaque = null,
    graceful_shutdown: ?*anyopaque = null,
    network_stats_reporter: ?*anyopaque = null,
    auto_repair: ?*anyopaque = null,
    incentive_slashing: ?*anyopaque = null,
    prometheus_exporter: ?*anyopaque = null,
    repair_rate_limiter: ?*anyopaque = null,
    token_staking: ?*anyopaque = null,
    peer_latency: ?*anyopaque = null,
    rs_repair: ?*anyopaque = null,
    metrics_http: ?*anyopaque = null,
    erasure_repair: ?*anyopaque = null,
    reputation_consensus: ?*anyopaque = null,
    offline_recovery: ?*anyopaque = null,
    local_index: ?*anyopaque = null,
    node_indexer: ?*anyopaque = null,
    discovery_cache: ?*anyopaque = null,
    stake_delegation: ?*anyopaque = null,
    shard_migration: ?*anyopaque = null,
    incentive_faucet: ?*anyopaque = null,
    leader_election: ?*anyopaque = null,
    region_topology: ?*anyopaque = null,
    cross_region_replication: ?*anyopaque = null,
    smart_contract_client: ?*anyopaque = null,
    gas_payment_pool: ?*anyopaque = null,
    slashing_escrow: ?*anyopaque = null,
    reward_allocator: ?*anyopaque = null,
    penalty_enforcer: ?*anyopaque = null,
    challenge_verifier: ?*anyopaque = null,
    prover_server: ?*anyopaque = null,
    witness_client: ?*anyopaque = null,
    consensus_participant: ?*anyopaque = null,
    finality_tracker: ?*anyopaque = null,
    state_sync: ?*anyopaque = null,
    block_proposer: ?*anyopaque = null,
    vote_aggregator: ?*anyopaque = null,
    fork_detector: ?*anyopaque = null,
    slashing_detector: ?*anyopaque = null,
    gossip_network: ?*anyopaque = null,
    transaction_pool: ?*anyopaque = null,
    mempool_monitor: ?*anyopaque = null,
    fee_market: ?*anyopaque = null,
    prometheus_http_endpoint: ?*anyopaque = null,
    histogram_registry: ?*anyopaque = null,
    health_check_server: ?*anyopaque = null,
    pprof_server: ?*anyopaque = null,
    vsa_encoder: ?*anyopaque = null,
    semantic_index: ?*anyopaque = null,
    vector_search: ?*anyopaque = null,

    pub fn init(allocator: std.mem.Allocator, wallet: *wallet_mod.Wallet, listen_port: u16) !*NetworkNode {
        const self = try allocator.create(NetworkNode);
        errdefer allocator.destroy(self);

        // Initialize discovery service
        const disc = try discovery.DiscoveryService.init(
            allocator,
            wallet.getNodeId(),
            wallet.getPublicKey(),
            listen_port,
        );
        errdefer disc.deinit();

        self.* = NetworkNode{
            .allocator = allocator,
            .wallet = wallet,
            .discovery_service = disc,
            .job_queue = JobQueue.init(),
            .status = .disconnected,
            .running = std.atomic.Value(bool).init(false),
            .job_server_thread = null,
            .job_server_socket = null,
            .listen_port = listen_port,
            .jobs_received = 0,
            .jobs_completed = 0,
            .jobs_failed = 0,
            .start_time = 0,
            .on_job_received = null,
        };

        return self;
    }

    pub fn deinit(self: *NetworkNode) void {
        self.stop();
        self.discovery_service.deinit();
        self.allocator.destroy(self);
    }

    /// Start network node
    pub fn start(self: *NetworkNode) !void {
        if (self.running.load(.acquire)) return;

        self.running.store(true, .release);
        self.status = .connecting;
        self.start_time = tri_time.timestamp();

        // Start discovery
        try self.discovery_service.start();

        // Start TCP job server
        try self.startJobServer();

        self.status = .ready;
    }

    /// Stop network node
    pub fn stop(self: *NetworkNode) void {
        self.running.store(false, .release);
        self.status = .disconnected;

        // Stop discovery
        self.discovery_service.stop();

        // Stop job server. Closing the listening socket is still what breaks
        // `jobServerLoop` out of its blocking accept.
        if (self.job_server_socket) |*server| {
            server.deinit(tri_io.get());
            self.job_server_socket = null;
        }

        if (self.job_server_thread) |thread| {
            thread.join();
            self.job_server_thread = null;
        }
    }

    /// Start TCP job server
    fn startJobServer(self: *NetworkNode) !void {
        const io = tri_io.get();

        // 0.16: the socket / setsockopt(SO_REUSEADDR) / bind / listen sequence
        // collapses into `IpAddress.listen`, which is the only way to get a
        // listening socket now that std.posix.socket and friends are gone.
        // `reuse_address` sets SO_REUSEADDR (and SO_REUSEPORT on POSIX);
        // `kernel_backlog` is the old `listen` backlog argument.
        const addr: std.Io.net.IpAddress = .{ .ip4 = .{ .bytes = .{ 0, 0, 0, 0 }, .port = self.listen_port } };
        var server = try addr.listen(io, .{
            .reuse_address = true,
            .kernel_backlog = 10,
        });
        errdefer {
            server.deinit(io);
            self.job_server_socket = null;
        }

        self.job_server_socket = server;
        self.job_server_thread = try std.Thread.spawn(.{}, jobServerLoop, .{self});
    }

    /// Job server loop - accepts connections and receives jobs
    fn jobServerLoop(self: *NetworkNode) void {
        const io = tri_io.get();
        if (self.job_server_socket == null) return;
        const server = &self.job_server_socket.?;

        while (self.running.load(.acquire)) {
            // 0.16: `accept` yields the connected `Stream` itself, and the
            // peer address rides along on the accepted socket instead of
            // coming back through a sockaddr out-parameter.
            const stream = server.accept(io) catch |err| {
                if (err == error.WouldBlock) continue;
                break;
            };
            defer stream.close(io);

            // Handle connection
            self.handleConnection(stream, stream.socket.address) catch |err| {
                std.log.debug("network: handle connection failed: {}", .{err});
            };
        }
    }

    /// Handle incoming connection
    fn handleConnection(self: *NetworkNode, stream: std.Io.net.Stream, client_addr: std.Io.net.IpAddress) !void {
        const io = tri_io.get();
        var buf: [65536]u8 = undefined;

        // 0.16: std.posix.recv/send went with the rest of the socket layer;
        // reads and writes go through Stream.Reader / Stream.Writer.
        var read_buf: [256]u8 = undefined;
        var stream_reader = stream.reader(io, &read_buf);
        const reader = &stream_reader.interface;

        // Read message header. `readSliceShort` returns fewer bytes than asked
        // for only at end of stream, which is the case the old recv-length
        // check was guarding -- but unlike a bare `recv` it also keeps reading
        // through a short TCP delivery instead of dropping the message.
        var header_buf: [protocol.MessageHeader.SIZE]u8 = undefined;
        const header_len = try reader.readSliceShort(&header_buf);
        if (header_len != protocol.MessageHeader.SIZE) return;

        const header = try protocol.MessageHeader.deserialize(&header_buf);

        // Read payload
        if (header.length > buf.len) return error.PayloadTooLarge;
        const payload_len = try reader.readSliceShort(buf[0..header.length]);
        if (payload_len != header.length) return;

        // Handle message by type
        switch (header.msg_type) {
            .job_request => {
                const job = try protocol.InferenceJob.deserialize(buf[0..payload_len], self.allocator);
                self.jobs_received += 1;

                // Add to queue
                const pending = PendingJob{
                    .job = job,
                    .received_at = tri_time.timestamp(),
                    .client_addr = client_addr,
                };
                _ = self.job_queue.push(pending);

                // Call callback if set
                if (self.on_job_received) |cb| {
                    cb(self, job);
                }
            },
            .heartbeat => {
                // Respond with our heartbeat
                const hb = protocol.Heartbeat{
                    .node_id = self.wallet.getNodeId(),
                    .timestamp = tri_time.timestamp(),
                    .jobs_completed = self.jobs_completed,
                    .uptime_seconds = @intCast(tri_time.timestamp() - self.start_time),
                    .status = if (self.job_queue.size() > 0) .busy else .online,
                };
                const payload = try hb.serialize(self.allocator);
                defer self.allocator.free(payload);

                const resp_header = protocol.MessageHeader{
                    .msg_type = .heartbeat,
                    .length = @intCast(payload.len),
                };
                // Stream.Writer buffers, so the flush is what puts the reply
                // on the wire.
                var write_buf: [1024]u8 = undefined;
                var stream_writer = stream.writer(io, &write_buf);
                const w = &stream_writer.interface;
                try w.writeAll(&resp_header.serialize());
                try w.writeAll(payload);
                try w.flush();
            },
            else => {},
        }
    }

    /// Get next pending job
    pub fn getNextJob(self: *NetworkNode) ?PendingJob {
        return self.job_queue.pop();
    }

    /// Submit job result
    pub fn submitResult(self: *NetworkNode, result: protocol.InferenceResult) !void {
        // Find client peer by node ID
        const peer = self.discovery_service.peers.getPeer(result.worker_id) orelse return error.PeerNotFound;

        const io = tri_io.get();

        // Connect to peer. 0.16: socket + connect collapse into
        // `IpAddress.connect`, which hands back the connected `Stream`.
        const stream = try peer.address.connect(io, .{ .mode = .stream });
        defer stream.close(io);

        // Send result
        const payload = try result.serialize(self.allocator);
        defer self.allocator.free(payload);

        const header = protocol.MessageHeader{
            .msg_type = .job_response,
            .length = @intCast(payload.len),
        };

        var write_buf: [1024]u8 = undefined;
        var stream_writer = stream.writer(io, &write_buf);
        const w = &stream_writer.interface;
        try w.writeAll(&header.serialize());
        try w.writeAll(payload);
        try w.flush();

        self.jobs_completed += 1;
    }

    /// Broadcast capabilities to network
    pub fn broadcastCapabilities(self: *NetworkNode, capabilities: protocol.NodeCapabilities) !void {
        const payload = try capabilities.serialize(self.allocator);
        defer self.allocator.free(payload);

        const header = protocol.MessageHeader{
            .msg_type = .capabilities,
            .length = @intCast(payload.len),
        };

        // Send to all known peers
        const peers = try self.discovery_service.getAlivePeers();
        defer self.allocator.free(peers);

        const io = tri_io.get();
        for (peers) |peer| {
            const stream = peer.address.connect(io, .{ .mode = .stream }) catch continue;
            defer stream.close(io);

            var write_buf: [1024]u8 = undefined;
            var stream_writer = stream.writer(io, &write_buf);
            const w = &stream_writer.interface;
            w.writeAll(&header.serialize()) catch continue;
            w.writeAll(payload) catch continue;
            w.flush() catch continue;
        }
    }

    /// Get network stats
    pub fn getStats(self: *NetworkNode) NetworkStats {
        const uptime = if (self.start_time > 0)
            @as(u64, @intCast(tri_time.timestamp() - self.start_time))
        else
            0;

        return NetworkStats{
            .status = self.status,
            .peer_count = self.discovery_service.getPeerCount(),
            .jobs_received = self.jobs_received,
            .jobs_completed = self.jobs_completed,
            .jobs_failed = self.jobs_failed,
            .pending_jobs = self.job_queue.size(),
            .uptime_seconds = uptime,
        };
    }

    /// Poll for network events (non-blocking)
    pub fn poll(self: *NetworkNode) void {
        // Prune dead peers periodically
        _ = self.discovery_service.peers.pruneDeadPeers();
    }
};

// ═══════════════════════════════════════════════════════════════════════════════
// NETWORK STATS
// ═══════════════════════════════════════════════════════════════════════════════

pub const NetworkStats = struct {
    status: NetworkStatus,
    peer_count: usize,
    jobs_received: u64,
    jobs_completed: u64,
    jobs_failed: u64,
    pending_jobs: usize,
    uptime_seconds: u64,
};

// ═══════════════════════════════════════════════════════════════════════════════
// TESTS
// ═══════════════════════════════════════════════════════════════════════════════

test "job queue operations" {
    var queue = JobQueue.init();

    const job = PendingJob{
        .job = undefined,
        .received_at = tri_time.timestamp(),
        .client_addr = .{ .ip4 = .{ .bytes = .{ 127, 0, 0, 1 }, .port = 9334 } },
    };

    try std.testing.expect(queue.push(job));
    try std.testing.expectEqual(@as(usize, 1), queue.size());

    const popped = queue.pop();
    try std.testing.expect(popped != null);
    try std.testing.expectEqual(@as(usize, 0), queue.size());
}
