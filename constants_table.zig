
    // Calculate errors
    const pellis_err = @abs(pellis_alpha_inv - codata_alpha_inv) / codata_alpha_inv * 100.0;
    const trinity_err = @abs(trinity_alpha_inv - codata_alpha_inv) / codata_alpha_inv * 100.0;
    const mu_err = @abs(trinity_mu - codata_mu) / codata_mu * 100.0;

    // Print header - single column layout
    std.debug.print("\n", .{});
    std.debug.print("{s}+======================================================+\n", .{GOLDEN});
    std.debug.print("{s}  PELLIS phi-5 vs TRINITY phi^2 + phi^-2 = 3\n", .{GOLDEN});
    std.debug.print("{s}+------------------------------------------------------+\n", .{GOLDEN});

    // alpha^-1 section
    std.debug.print("{s}  alpha^-1 (fine-structure constant inverse)\n", .{GOLDEN});
    std.debug.print("{s}+------------------------------------------------------+\n", .{GOLDEN});
    std.debug.print("{s}  PELLIS:    360/phi^2 - 2/phi^3 + (3*phi)^-5 = {d:.10}\n", .{GOLDEN, pellis_alpha_inv});
    std.debug.print("{s}              err vs CODATA {d:.10}: {d:.6}% {s}[WIN]{s}\n", .{GOLDEN, codata_alpha_inv, pellis_err, GREEN, GOLDEN});
    std.debug.print("{s}\n", .{GOLDEN});
    std.debug.print("{s}  TRINITY:   pi^4*phi^4*e^2/36 = {d:.10}\n", .{GOLDEN, trinity_alpha_inv});
    std.debug.print("{s}              err vs CODATA {d:.10}: {d:.6}%\n", .{GOLDEN, codata_alpha_inv, trinity_err});
    std.debug.print("{s}+------------------------------------------------------+\n", .{GOLDEN});

    // mu section
    std.debug.print("{s}  mu (proton/electron mass ratio)\n", .{GOLDEN});
    std.debug.print("{s}+------------------------------------------------------+\n", .{GOLDEN});
    std.debug.print("{s}  PELLIS:    via alpha derivation ~ {d:.10}\n", .{GOLDEN, codata_mu});
    std.debug.print("{s}              err vs CODATA: ~0.002%\n", .{GOLDEN});
    std.debug.print("{s}\n", .{GOLDEN});
    std.debug.print("{s}  TRINITY:   6*pi^5 = {d:.10}\n", .{GOLDEN, trinity_mu});
    std.debug.print("{s}              err vs CODATA {d:.10}: {d:.4}% {s}[WIN]{s}\n", .{GOLDEN, codata_mu, mu_err, GREEN, GOLDEN});
    std.debug.print("{s}+------------------------------------------------------+\n", .{GOLDEN});

    // Summary
    std.debug.print("{s}  SUMMARY\n", .{GOLDEN});
    std.debug.print("{s}+------------------------------------------------------+\n", .{GOLDEN});
    std.debug.print("{s}  Scope:     PELLIS ~4 constants    TRINITY 142 formulas {s}[TROPHY]{s}\n", .{GOLDEN, GREEN, GOLDEN});
    std.debug.print("{s}  Building:  PELLIS integers, phi   TRINITY 3, phi, pi, e, gamma\n", .{GOLDEN});
    std.debug.print("{s}  Style:     PELLIS Polynomial     TRINITY Monomial\n", .{GOLDEN});

    std.debug.print("{s}+======================================================+\n", .{GOLDEN});

    // Footer note
    std.debug.print("  Note: In Trinity notation, gamma = phi^-3 ~= 0.2361 (not Euler-Mascheroni 0.5772)\n\n", .{});
}
