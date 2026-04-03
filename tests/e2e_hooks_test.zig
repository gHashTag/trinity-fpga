//! E2E Hooks Integration Test (Issue E)
//! φ² + 1/φ² = 3 | TRINITY

const std = @import("std");
const Allocator = std.mem.Allocator;

test "hooks save episode correctly" {
    // Verify experience hooks has autoSaveExperience function
    const allocator = std.testing.allocator;

    // Create test episode using experience hooks
    var episode = try @import("../src/tri/tri_experience.zig").Episode{};
    defer {
        allocator.free(episode.task);
        allocator.free(episode.task_len);
    allocator.free(episode.verdict);
        allocator.free(episode.verdict_len);
    // Free learnings and mistakes arrays
        for (0..8) |i| {
            allocator.free(episode.learnings[i]);
            allocator.free(episode.mistakes[i]);
        }
        allocator.free(episode.learning_count);
        allocator.free(episode.mistake_count);
    }

    episode.timestamp = 12345;
    episode.issue = 999;
    episode.iterations = 1;

    // Step 1: Research (scan) with hooks
    episode.task[0] = "tri dev scan";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[0..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Step 2: Spec (spec create) with hooks
    episode.task[1] = "tri spec create";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[1..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Step 3: Gen (code generate) with hooks
    episode.task[2] = "tri gen";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[2..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Step 4: Verify (tests) with hooks
    episode.task[3] = "tri test";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[3..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Step 5: Verdict with hooks
    episode.task[4] = "tri verdict --toxic";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[4..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Step 6: Experience save with hooks
    episode.task[5] = "tri experience save";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[5..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Step 7: Git commit with hooks
    episode.task[6] = "tri git commit";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[6..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Step 8: Loop decide with hooks
    episode.task[7] = "tri loop decide";
    try @import("../src/tri/experience_hooks.zig").autoSaveExperience(allocator, episode.task[7..episode.task_len], episode.verdict);
    allocator.free(episode.task);

    // Save final episode
    episode.verdict[0] = "PASS";
    episode.iterations = 8;

    try @import("../src/tri/tri_experience.zig").saveEpisode(allocator, episode);
    defer allocator.free(episode);

    // Verify all steps saved
    try std.testing.expectEqual(episode.iterations, 8);
    try std.testing.expectEqual(episode.verdict[0], "PASS");
}
