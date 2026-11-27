`include "phase_monitor.svh"

module dw_emmc_inline_phase_probe;
    timeunit 1fs;
    timeprecision 1fs;

    bit chip_clk, stopped;
    wire card_clk, late_clk;
    assign #350ps card_clk = chip_clk;
    assign #1100ps late_clk = chip_clk;

    phase_monitor normal(.link_chip_clk(chip_clk), .link_card_clk(card_clk));
    phase_monitor late(.link_chip_clk(chip_clk), .link_card_clk(late_clk));
    phase_monitor reversed(.link_chip_clk(card_clk), .link_card_clk(chip_clk));
    phase_monitor direct(.link_chip_clk(chip_clk), .link_card_clk(chip_clk));
    phase_monitor no_edges(.link_chip_clk(stopped), .link_card_clk(stopped));

    always #2500ps chip_clk = ~chip_clk;

    initial begin
        string problem;
        longint period_fs, delay_fs;
        time started;

        #100ps;
        normal.measure_link_clock(1000, period_fs, delay_fs, problem);
        if (problem != "" || period_fs != 5_000_000 || delay_fs != 350_000)
            $fatal(1, "incorrect link period/propagation: %0d %0d %s", period_fs, delay_fs, problem);
        late.measure_link_clock(1000, period_fs, delay_fs, problem);
        if (problem == "")
            $fatal(1, "over-limit propagation was accepted");
        reversed.measure_link_clock(1000, period_fs, delay_fs, problem);
        if (problem == "")
            $fatal(1, "reversed observation points were accepted");
        direct.measure_link_clock(1000, period_fs, delay_fs, problem);
        if (problem != "" || delay_fs != 0)
            $fatal(1, "direct connection did not measure zero: %s", problem);
        normal.measure_link_clock(0, period_fs, delay_fs, problem);
        if (problem == "")
            $fatal(1, "missing propagation bound was accepted");
        started = $time;
        no_edges.measure_link_clock(1000, period_fs, delay_fs, problem);
        if (problem == "" || $time - started != 10us)
            $fatal(1, "stopped clock did not return an observation error");
        $display("INLINE_PHASE_PROBE_PASS");
        $finish;
    end
endmodule
