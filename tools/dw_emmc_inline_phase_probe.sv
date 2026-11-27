`include "phase_monitor.svh"

module dw_emmc_inline_phase_probe;
    timeunit 1fs;
    timeprecision 1fs;

    logic ref_clk = 0;
    logic tx_clk = 0;
    logic rx_clk = 0;
    logic fast_clk = 0;
    logic distorted_clk = 0;
    bit stop_rx;
    bit use_fast;
    bit use_distorted;
    phase_monitor monitor_if(.phase_tx_ref(ref_clk),
        .phase_tx_clk(use_distorted ? distorted_clk : tx_clk),
        .phase_rx_ref(ref_clk), .phase_rx_clk(use_fast ? fast_clk : rx_clk));

    always begin
        #1ns ref_clk = 1;
        #3ns ref_clk = 0;
        #1ns;
    end
    initial begin
        #250ps;
        forever begin
            #1ns tx_clk = 1;
            #3ns tx_clk = 0;
            #1ns;
        end
    end
    always begin
        #750ps rx_clk = !stop_rx;
        #3ns rx_clk = 0;
        #1250ps;
    end
    always #2ns fast_clk = ~fast_clk;
    always begin
        #1250ps distorted_clk = 1;
        #2ns distorted_clk = 0;
        #1750ps;
    end

    task automatic check(input bit read_path, input bit both_edges,
        input longint expected, input string expected_problem);
        longint shift_fs, frequency_hz;
        string problem;
        monitor_if.measure_phase(read_path, both_edges, shift_fs, frequency_hz, problem);
        if (problem != expected_problem ||
            (problem == "" && (shift_fs != expected || frequency_hz != 200_000_000)))
            $fatal(1, "expected %0d fs (%s), got %0d fs at %0d Hz (%s)",
                expected, expected_problem, shift_fs, frequency_hz, problem);
    endtask

    initial begin
        time begin_measurement;
        #100ps;
        check(0, 1, -250_000, "");
        check(1, 0, 250_000, "");
        use_distorted = 1;
        #100ps;
        check(0, 1, 0, "phase drifts or the selected edges require different corrections");
        use_fast = 1;
        #100ps;
        check(1, 0, 0, "phase clock periods differ or are unstable");
        use_fast = 0;
        stop_rx = 1;
        #10ns;
        begin_measurement = $time;
        check(1, 0, 0, "phase clock pair did not supply enough edges");
        if ($time - begin_measurement != 10us)
            $fatal(1, "stopped clock did not exit at the measurement limit");
        $display("INLINE_PHASE_PROBE_PASS");
        $finish;
    end
endmodule
