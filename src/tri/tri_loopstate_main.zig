// tri_loopstate_main — standalone entry point for tri_loopstate.zig.
//
// The whole-CLI build (src/tri/main.zig) is blocked on the Zig-0.16
// Io-threading migration (see STATE.json anomaly A1): there is no build.zig
// anywhere in this repo that targets it. This file sidesteps that by being
// its own tiny `pub fn main`, built directly:
//
//   zig build-exe src/tri/tri_loopstate_main.zig -femit-bin=tri-loopstate
//   ./tri-loopstate status
//   ./tri-loopstate check
//
// Once the Io-threading decision lands and main.zig can dispatch to it, this
// file's body is what a `tri loopstate <sub>` case should call -- do not
// duplicate the logic there, wire this in.
//
// Dmitrii Vasilev / @gHashTag

const std = @import("std");
const loopstate = @import("tri_loopstate.zig");
const dashboard = @import("loop_dashboard.zig");

fn usage() void {
    std.debug.print(
        \\usage: tri-loopstate <status|check|tripwire|bump|render|record> [--state PATH]
        \\                     [--dashboard PATH] [--out PATH] [--note TEXT]
        \\                     [--kind done|anomaly] [--entry PATH]
        \\
        \\  status     print the current iteration, done count, and next actionable backlog item
        \\  check      recompute live backlog/anomaly counts from STATE.json and diff them
        \\             against the dashboard's readout block; exits 1 if a drift is found
        \\  tripwire   fresh disk/drift/decision-gridlock reading, updates the dashboard's
        \\             halt banner accordingly, and exits 1 if any tripwire is active
        \\             (exit 1 also on any read/parse failure -- treat that as a halt too)
        \\  bump       increment loop.iteration in STATE.json and print the new value.
        \\             Replaces the "MANDATORY SELF-CHECK" in the continuity protocol that
        \\             asked a human to remember; it did not, for nine consecutive
        \\             iterations (anomaly A24, a recurrence of A7 at ~10x the scale).
        \\  record     append a done[] or anomalies[] entry from --entry PATH (a JSON
        \\             object), assigning the next free id itself. The id is DERIVED, never
        \\             passed in: every iteration used to append these by hand through a
        \\             throwaway script that also hand-asserted the id was free, which is
        \\             the same shape as the iteration counter before `bump` (see A24).
        \\  render     regenerate the status dashboard from STATE.json (default --out
        \\             .trinity/loop/status.html). Derived, so its numbers cannot drift
        \\             from the state file the way a hand-edited page does.
        \\
    , .{});
}

pub fn main(init: std.process.Init) !u8 {
    const gpa = init.gpa;
    const arena = init.arena.allocator();
    const argv = try init.minimal.args.toSlice(arena);

    if (argv.len < 2) {
        usage();
        return 1;
    }
    const cmd = argv[1];

    var state_path: []const u8 = loopstate.default_state_path;
    var dashboard_path: []const u8 = ".trinity/loop/dashboard.html";
    var out_path: []const u8 = dashboard.default_output_path;
    var note: []const u8 = "";
    var kind: []const u8 = "";
    var entry_path: []const u8 = "";
    var i: usize = 2;
    while (i < argv.len) : (i += 1) {
        if (std.mem.eql(u8, argv[i], "--state") and i + 1 < argv.len) {
            i += 1;
            state_path = argv[i];
        } else if (std.mem.eql(u8, argv[i], "--dashboard") and i + 1 < argv.len) {
            i += 1;
            dashboard_path = argv[i];
        } else if (std.mem.eql(u8, argv[i], "--out") and i + 1 < argv.len) {
            i += 1;
            out_path = argv[i];
        } else if (std.mem.eql(u8, argv[i], "--note") and i + 1 < argv.len) {
            i += 1;
            note = argv[i];
        } else if (std.mem.eql(u8, argv[i], "--kind") and i + 1 < argv.len) {
            i += 1;
            kind = argv[i];
        } else if (std.mem.eql(u8, argv[i], "--entry") and i + 1 < argv.len) {
            i += 1;
            entry_path = argv[i];
        }
    }

    const state_bytes = std.Io.Dir.cwd().readFileAlloc(init.io, state_path, gpa, .limited(16 << 20)) catch |err| {
        std.debug.print("error: could not read {s}: {t}\n", .{ state_path, err });
        return 1;
    };
    defer gpa.free(state_bytes);

    var st = loopstate.parse(gpa, state_bytes) catch |err| {
        std.debug.print("error: {s} did not parse as loop state: {t}\n", .{ state_path, err });
        return 1;
    };
    defer st.deinit();

    if (std.mem.eql(u8, cmd, "status")) {
        const s = try loopstate.renderStatus(gpa, &st);
        defer gpa.free(s);
        std.debug.print("{s}", .{s});
        return 0;
    }

    if (std.mem.eql(u8, cmd, "record")) {
        const section: []const u8, const prefix: []const u8 =
            if (std.mem.eql(u8, kind, "done"))
                .{ "done", "D" }
            else if (std.mem.eql(u8, kind, "anomaly"))
                .{ "anomalies", "A" }
            else {
                std.debug.print("error: --kind must be 'done' or 'anomaly', got '{s}'\n", .{kind});
                return 1;
            };

        if (entry_path.len == 0) {
            std.debug.print("error: record needs --entry PATH (a JSON object)\n", .{});
            return 1;
        }

        const entry_bytes = std.Io.Dir.cwd().readFileAlloc(init.io, entry_path, gpa, .limited(4 << 20)) catch |err| {
            std.debug.print("error: could not read {s}: {t}\n", .{ entry_path, err });
            return 1;
        };
        defer gpa.free(entry_bytes);

        const entry_doc = std.json.parseFromSlice(std.json.Value, gpa, entry_bytes, .{}) catch |err| {
            std.debug.print("error: {s} is not valid JSON: {t}\n", .{ entry_path, err });
            return 1;
        };
        defer entry_doc.deinit();

        const res = loopstate.recordEntry(gpa, &st, section, prefix, entry_doc.value) catch |err| {
            std.debug.print("error: could not append to {s}: {t}\n", .{ section, err });
            return 1;
        };
        defer gpa.free(res.json);

        std.Io.Dir.cwd().writeFile(init.io, .{ .sub_path = state_path, .data = res.json }) catch |err| {
            std.debug.print("error: could not write {s}: {t}\n", .{ state_path, err });
            return 1;
        };

        std.debug.print("recorded {s} in {s}\n", .{ res.id, section });
        return 0;
    }

    if (std.mem.eql(u8, cmd, "bump")) {
        const before = st.iteration;
        const updated = loopstate.bumpIteration(gpa, &st) catch |err| {
            std.debug.print("error: could not increment loop.iteration: {t}\n", .{err});
            return 1;
        };
        defer gpa.free(updated);

        std.Io.Dir.cwd().writeFile(init.io, .{ .sub_path = state_path, .data = updated }) catch |err| {
            // Reported, never swallowed: a bump that silently failed to write
            // would reproduce the exact drift this command exists to end, while
            // printing the number that proves it worked.
            std.debug.print("error: could not write {s}: {t}\n", .{ state_path, err });
            return 1;
        };
        std.debug.print("iteration {d} -> {d}\n", .{ before, st.iteration });
        return 0;
    }

    if (std.mem.eql(u8, cmd, "render")) {
        const html = dashboard.render(gpa, &st, note) catch |err| {
            std.debug.print("error: could not render dashboard: {t}\n", .{err});
            return 1;
        };
        defer gpa.free(html);

        std.Io.Dir.cwd().writeFile(init.io, .{ .sub_path = out_path, .data = html }) catch |err| {
            std.debug.print("error: could not write {s}: {t}\n", .{ out_path, err });
            return 1;
        };

        // Verify what was actually written, not what was about to be: the whole
        // point of a generated page is that the tooling can read it back, and
        // the cheapest moment to find out it cannot is right now.
        const live = loopstate.liveCounts(&st);
        const report = try loopstate.checkDrift(gpa, live, html);
        defer gpa.free(report);
        if (std.mem.indexOf(u8, report, "DRIFT") != null or std.mem.indexOf(u8, report, "MISSING") != null) {
            std.debug.print("error: rendered {s} but it does not read back cleanly:\n{s}", .{ out_path, report });
            return 1;
        }

        std.debug.print("rendered {s} ({d} bytes) at iteration {d}\n", .{ out_path, html.len, st.iteration });
        return 0;
    }

    if (std.mem.eql(u8, cmd, "check")) {
        const dashboard_bytes = std.Io.Dir.cwd().readFileAlloc(init.io, dashboard_path, gpa, .limited(16 << 20)) catch |err| {
            std.debug.print("error: could not read {s}: {t}\n", .{ dashboard_path, err });
            return 1;
        };
        defer gpa.free(dashboard_bytes);

        const live = loopstate.liveCounts(&st);
        const report = try loopstate.checkDrift(gpa, live, dashboard_bytes);
        defer gpa.free(report);
        std.debug.print("{s}", .{report});
        return if (std.mem.indexOf(u8, report, "DRIFT") != null or std.mem.indexOf(u8, report, "MISSING") != null) 1 else 0;
    }

    if (std.mem.eql(u8, cmd, "tripwire")) {
        const dashboard_bytes = std.Io.Dir.cwd().readFileAlloc(init.io, dashboard_path, gpa, .limited(16 << 20)) catch |err| {
            std.debug.print("error: could not read {s}: {t}\n", .{ dashboard_path, err });
            return 1;
        };
        defer gpa.free(dashboard_bytes);

        const thresholds = loopstate.readDiskThresholds(&st);
        var disk_error: ?anyerror = null;
        const free_gib: f64 = loopstate.freeGiB(".") catch |err| blk: {
            disk_error = err;
            break :blk 0.0;
        };
        const raw_disk_tier: loopstate.DiskTier = if (disk_error != null) .halt else loopstate.evalDiskTier(free_gib, thresholds);

        // B21: hysteresis + flap detection. A read failure is always
        // reported as an immediate halt (matches the pre-B21 behavior) --
        // hysteresis only smooths the exit out of a genuine disk-halt, it
        // never delays or masks a fresh failure to read the disk at all.
        const prev_hysteresis = loopstate.readDiskHysteresisState(&st);
        const hyst_result = if (disk_error != null)
            loopstate.HysteresisResult{ .effective_tier = .halt, .new_state = .{ .was_halted = true, .recovery_streak = 0 } }
        else
            loopstate.applyDiskHysteresis(raw_disk_tier, prev_hysteresis, thresholds.recovery_confirmations);
        const disk_tier = hyst_result.effective_tier;

        const prev_episodes = try loopstate.readHaltEpisodes(gpa, &st);
        defer gpa.free(prev_episodes);
        const starting_new_episode = raw_disk_tier == .halt and !prev_hysteresis.was_halted;
        const new_episodes = try loopstate.updateHaltEpisodes(gpa, prev_episodes, st.iteration, starting_new_episode, thresholds.flap_window_iterations);
        defer gpa.free(new_episodes);
        const is_flapping = loopstate.detectFlap(new_episodes, st.iteration, thresholds.flap_window_iterations, thresholds.flap_threshold);

        const new_state_bytes = try loopstate.writeTripwireHysteresis(gpa, &st, hyst_result.new_state, new_episodes);
        defer gpa.free(new_state_bytes);
        std.Io.Dir.cwd().writeFile(init.io, .{ .sub_path = state_path, .data = new_state_bytes }) catch |err| {
            std.debug.print("error: could not write {s}: {t}\n", .{ state_path, err });
            return 1;
        };

        const live = loopstate.liveCounts(&st);
        const first_report = try loopstate.checkDrift(gpa, live, dashboard_bytes);
        defer gpa.free(first_report);

        // A plain numeric mismatch is mechanical and safe to fix every time
        // it's found -- both inputs are entirely under the loop's own
        // control. Only a heal that DOESN'T stick (a MISSING label, or one
        // that's still wrong after the rewrite) counts as a real drift
        // tripwire; a heal that works is not a halt.
        var heal = try loopstate.autoHealDrift(gpa, live, dashboard_bytes);
        defer heal.deinit(gpa);
        const drift_report = heal.final_report;
        const dashboard_for_banner = heal.healed_html;
        const healed = !std.mem.eql(u8, first_report, "checked, consistent\n") and
            std.mem.eql(u8, drift_report, "checked, consistent\n");

        var gate = try loopstate.decisionGateStatus(gpa, &st);
        defer gate.deinit(gpa);

        const reasons = loopstate.evaluateTripwires(disk_tier, drift_report, gate.status);

        var detail: std.ArrayList(u8) = .empty;
        defer detail.deinit(gpa);
        if (disk_error != null) {
            try detail.print(gpa, "disk read FAILED ({t}), treating as halt; ", .{disk_error.?});
        } else if (reasons.disk and raw_disk_tier == .halt) {
            try detail.print(gpa, "disk {d:.2} GiB free (< {d:.2} threshold); ", .{ free_gib, thresholds.halt_gib });
        } else if (reasons.disk) {
            try detail.print(gpa, "disk recovered to {d:.2} GiB free but held at halt pending confirmation ({d}/{d} consecutive non-halt readings); ", .{ free_gib, hyst_result.new_state.recovery_streak, thresholds.recovery_confirmations });
        }
        if (is_flapping) {
            try detail.print(gpa, "disk halt is flapping ({d}+ episodes within the last {d} iterations); ", .{ thresholds.flap_threshold, thresholds.flap_window_iterations });
        }
        if (reasons.drift) try detail.print(gpa, "drift (unrecoverable, did not auto-heal): {s}; ", .{std.mem.trim(u8, drift_report, "\n")});
        if (reasons.decision) {
            try detail.print(gpa, "decision-gated on: ", .{});
            for (gate.gated_ids.items, 0..) |id, idx| {
                if (idx > 0) try detail.print(gpa, ", ", .{});
                try detail.print(gpa, "{s}", .{id});
            }
            try detail.print(gpa, "; ", .{});
        }

        const banner = try loopstate.renderHaltBanner(gpa, reasons, detail.items);
        defer gpa.free(banner);
        const new_dashboard = loopstate.injectHaltBanner(gpa, dashboard_for_banner, banner) catch |err| {
            std.debug.print("error: could not update halt banner in {s}: {t}\n", .{ dashboard_path, err });
            return 1;
        };
        defer gpa.free(new_dashboard);
        std.Io.Dir.cwd().writeFile(init.io, .{ .sub_path = dashboard_path, .data = new_dashboard }) catch |err| {
            std.debug.print("error: could not write {s}: {t}\n", .{ dashboard_path, err });
            return 1;
        };

        if (disk_tier != raw_disk_tier) {
            std.debug.print("disk:     {s} (raw reading: {s}, held by hysteresis -- {d}/{d} confirmations) ({d:.2} GiB free, halt<{d:.2} warn<{d:.2})\n", .{ @tagName(disk_tier), @tagName(raw_disk_tier), hyst_result.new_state.recovery_streak, thresholds.recovery_confirmations, free_gib, thresholds.halt_gib, thresholds.warn_gib });
        } else {
            std.debug.print("disk:     {s} ({d:.2} GiB free, halt<{d:.2} warn<{d:.2})\n", .{ @tagName(disk_tier), free_gib, thresholds.halt_gib, thresholds.warn_gib });
        }
        if (is_flapping) {
            std.debug.print("flap:     WARNING -- {d}+ halt episodes within the last {d} iterations ({d} tracked)\n", .{ thresholds.flap_threshold, thresholds.flap_window_iterations, new_episodes.len });
        }
        if (healed) {
            std.debug.print("drift:    auto-healed this run -- was: {s}\n", .{std.mem.trim(u8, first_report, "\n")});
        }
        std.debug.print("drift:    {s}", .{drift_report});
        std.debug.print("decision: {s}", .{@tagName(gate.status)});
        if (gate.gated_ids.items.len > 0) {
            std.debug.print(" (gated: ", .{});
            for (gate.gated_ids.items, 0..) |id, idx| {
                if (idx > 0) std.debug.print(", ", .{});
                std.debug.print("{s}", .{id});
            }
            std.debug.print(")", .{});
        }
        std.debug.print("\n", .{});
        std.debug.print("verdict:  {s}\n", .{if (reasons.any()) "HALTED" else "RUNNING"});

        return if (reasons.any()) 1 else 0;
    }

    usage();
    return 1;
}
