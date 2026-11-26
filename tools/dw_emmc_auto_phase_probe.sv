`timescale 1ns/1ps
`include "uvm_macros.svh"
import uvm_pkg::*;

`include "core/clock_phase_types.sv"

import Emmc_ctrl_clock_phase_types::*;
typedef enum {HIGH_SPEED_SDR, HIGH_SPEED_DDR, HS200, HS400, LEGACY} bus_speed_mode_e;

interface Emmc_ctrl_interface;
endinterface

class Emmc_ctrl_scoreboard;
endclass

class boot_settings;
    int default_data_width = 8;
    bus_speed_mode_e default_bus_speed_mode = HS400;
    int voltage = 2;
    int frequence_legacy = 26000000;
    int frequence_high_speed_sdr = 50000000;
    int frequence_high_speed_ddr = 50000000;
    int frequence_hs200 = 192000000;
    int frequence_hs400 = 196000000;
endclass

class Emmc_ctrl_settings;
    boot_settings boot_cfg = new;
    virtual Emmc_ctrl_interface vif;
    bit clock_phase_auto_enable = 1;
    int clock_phase_max_probes = 10;
    int clock_phase_confirm_samples = 1;
    int clock_phase_scan_timeout_us = 10;
    int clock_phase_restore_timeout_us = 5;
endclass

class Emmc_ctrl_context;
    bit has_initialized = 1;
    int data_width_cur = 1;
    int frequency_hz;
    bus_speed_mode_e bus_speed_mode_cur = LEGACY;
    int trace[$];
endclass

`include "component/callback.sv"
`include "core/clock_phase_calibrator.sv"
`include "component/sequencer.sv"

class Emmc_ctrl_base_seq extends uvm_sequence;
    `uvm_declare_p_sequencer(Emmc_ctrl_sequencer)
    typedef $unit::bus_speed_mode_e bus_speed_mode_e;
    localparam bus_speed_mode_e HS200 = $unit::HS200;
    localparam bus_speed_mode_e HS400 = $unit::HS400;
    localparam bus_speed_mode_e HIGH_SPEED_SDR = $unit::HIGH_SPEED_SDR;
    localparam bus_speed_mode_e HIGH_SPEED_DDR = $unit::HIGH_SPEED_DDR;
    localparam bus_speed_mode_e LEGACY = $unit::LEGACY;
    localparam int V1_8 = 2;
    localparam int V1_2 = 3;
    Emmc_ctrl_settings settings;
    Emmc_ctrl_context ctx;

    function new(string name = "base");
        super.new(name);
    endfunction

    function void pre_randomize();
        settings = p_sequencer.settings;
        ctx = p_sequencer.ctx;
    endfunction
endclass

class frequency_request;
    rand int frequence;
    int default_frequency;
    constraint cfg { soft frequence == default_frequency; }
endclass

class Emmc_ctrl_frequence_set_operation_seq extends Emmc_ctrl_base_seq;
    `uvm_object_utils(Emmc_ctrl_frequence_set_operation_seq)
    rand frequency_request freq_set_request = new;

    function new(string name = "frequency");
        super.new(name);
    endfunction

    function void pre_randomize();
        super.pre_randomize();
        case (ctx.bus_speed_mode_cur)
            HS200: freq_set_request.default_frequency = settings.boot_cfg.frequence_hs200;
            HS400: freq_set_request.default_frequency = settings.boot_cfg.frequence_hs400;
            HIGH_SPEED_SDR: freq_set_request.default_frequency = settings.boot_cfg.frequence_high_speed_sdr;
            default: freq_set_request.default_frequency = settings.boot_cfg.frequence_legacy;
        endcase
    endfunction

    task body();
        ctx.trace.push_back(freq_set_request.frequence);
        ctx.frequency_hz = freq_set_request.frequence;
        p_sequencer.note_bus_frequency(freq_set_request.frequence);
    endtask
endclass

class switch_request;
    rand bus_speed_mode_e bus_speed_mode;
    rand int data_width;
    constraint supported_timing {
        data_width inside {1, 4, 8};
        bus_speed_mode inside {LEGACY, HIGH_SPEED_SDR, HIGH_SPEED_DDR, HS200, HS400};
    }
endclass

class Emmc_ctrl_switch_hs_timing_command_seq extends Emmc_ctrl_base_seq;
    `uvm_object_utils(Emmc_ctrl_switch_hs_timing_command_seq)
    rand switch_request cmd_request = new;

    function new(string name = "timing");
        super.new(name);
    endfunction

    task body();
        ctx.bus_speed_mode_cur = cmd_request.bus_speed_mode;
        if ($test$plusargs("trace_config"))
            $display("mock timing: %s", ctx.bus_speed_mode_cur.name());
    endtask
endclass

class Emmc_ctrl_switch_bus_width_command_seq extends Emmc_ctrl_base_seq;
    `uvm_object_utils(Emmc_ctrl_switch_bus_width_command_seq)
    rand switch_request cmd_request = new;

    function new(string name = "width");
        super.new(name);
    endfunction

    task body();
        ctx.data_width_cur = cmd_request.data_width;
        if ($test$plusargs("trace_config"))
            $display("mock width: %0d", ctx.data_width_cur);
    endtask
endclass

`include "sequence/flow/switch_bus.sv"

class auto_adapter extends Emmc_ctrl_callback;
    Emmc_ctrl_context ctx;
    operating_point_t active_point;
    int revision;
    int training_probes;
    int transfer_probes;
    bit stall_probe;
    bit probe_running;
    bit reject_transfer;
    taps_t current = '{0};

    function bit clock_phase_enabled();
        return 1;
    endfunction

    function int clock_phase_revision();
        return revision;
    endfunction

    function bit clock_phase_accepts(input operating_point_t point);
        return point.speed_mode != int'(HIGH_SPEED_SDR);
    endfunction

    function void clock_phase_select(input operating_point_t point);
        if (ctx.bus_speed_mode_cur != point.speed_mode || ctx.data_width_cur != point.data_width ||
            ctx.frequency_hz != point.frequency_hz || point.voltage != 2)
            $fatal(1, "adapter called before the operating point was programmed");
        active_point = point;
        ctx.trace.push_back(point.protocol == PHASE_EMMC_HS200_CMD21 ? -200 : -400);
    endfunction

    function void clock_phase_describe(output axes_t axes);
        axes = '{'{"sample", 0, 3, 0}};
    endfunction

    task clock_phase_capture(output taps_t taps, output bit ok);
        taps = current;
        ok = 1;
    endtask

    task clock_phase_apply(input taps_t taps, output bit ok);
        current = taps;
        ok = 1;
    endtask

    task clock_phase_probe(input int group_id, output probe_e outcome);
        if (active_point.protocol == PHASE_EMMC_HS200_CMD21 && ctx.bus_speed_mode_cur == HS200)
            training_probes++;
        else if (active_point.protocol == PHASE_EMMC_HS400_TRANSFER && ctx.bus_speed_mode_cur == HS400)
            transfer_probes++;
        else
            $fatal(1, "wrong tuning protocol");
        if (stall_probe) begin
            stall_probe = 0;
            probe_running = 1;
            #10ns;
            if (int'(ctx.bus_speed_mode_cur) != active_point.speed_mode)
                $fatal(1, "another sequence reprogrammed the bus during a probe");
            probe_running = 0;
        end
        outcome = current[0] == 1 && !(reject_transfer && active_point.protocol == PHASE_EMMC_HS400_TRANSFER)
            ? PROBE_PASSED : PROBE_REJECTED;
    endtask
endclass

module dw_emmc_auto_phase_probe;
    task automatic switch_bus(input Emmc_ctrl_sequencer sqr, input bus_speed_mode_e mode = HS400);
        Emmc_ctrl_switch_bus_seq seq;

        seq = new;
        seq.set_item_context(null, sqr);
        if (!seq.randomize() with {bus_speed_mode == local::mode; data_width == 8;})
            $fatal(1, "switch randomize failed");
        seq.start(sqr);
    endtask

    initial begin
        Emmc_ctrl_sequencer sqr;
        auto_adapter adapter;
        Emmc_ctrl_callback other_callback;
        int bypass_trace[$];
        int first_trace[$];
        int concurrent_trace[$];

        sqr = new("test_sqr", null);
        sqr.settings = new;
        sqr.ctx = new;
        adapter = new;
        adapter.ctx = sqr.ctx;
        bypass_trace = '{6000000, 196000000};
        first_trace = '{6000000, 192000000, -200, 6000000, 196000000, -400};
        concurrent_trace = first_trace;
        concurrent_trace.push_back(6000000);
        concurrent_trace.push_back(50000000);

        switch_bus(sqr);
        if (sqr.ctx.trace != bypass_trace)
            $fatal(1, "no adapter trace: %p; mode=%s width=%0d",
                sqr.ctx.trace, sqr.ctx.bus_speed_mode_cur.name(), sqr.ctx.data_width_cur);
        other_callback = new("legacy_cpu_callback");
        uvm_callbacks#(Emmc_ctrl_sequencer, Emmc_ctrl_callback)::add(sqr, other_callback);
        sqr.ctx.trace.delete();
        switch_bus(sqr);
        if (sqr.ctx.trace != bypass_trace)
            $fatal(1, "a callback without phase overrides changed the normal flow");
        uvm_callbacks#(Emmc_ctrl_sequencer, Emmc_ctrl_callback)::add(sqr, adapter);
        sqr.settings.clock_phase_auto_enable = 0;
        sqr.ctx.trace.delete();
        switch_bus(sqr);
        if (sqr.ctx.trace != bypass_trace || adapter.training_probes || adapter.transfer_probes)
            $fatal(1, "disabled adapter changed the normal flow");
        sqr.settings.clock_phase_auto_enable = 1;
        sqr.ctx.trace.delete();
        if ($test$plusargs("duplicate_callback")) begin
            auto_adapter duplicate = new;
            duplicate.set_name("duplicate_phase_callback");
            uvm_callbacks#(Emmc_ctrl_sequencer, Emmc_ctrl_callback)::add(sqr, duplicate);
            switch_bus(sqr);
            $fatal(1, "duplicate callback returned into the normal flow");
        end
        if ($test$plusargs("reject_transfer")) begin
            adapter.reject_transfer = 1;
            switch_bus(sqr);
            $fatal(1, "no-window phase returned into the normal flow");
        end
        switch_bus(sqr);
        if (sqr.ctx.trace != first_trace || adapter.training_probes != 4 || adapter.transfer_probes != 4)
            $fatal(1, "wrong automatic HS400 entry: %p", sqr.ctx.trace);
        // The mode remains stable; prepare should only re-read the programmed taps.
        sqr.ctx.trace.pop_back();
        switch_bus(sqr);
        if (sqr.ctx.trace != first_trace || adapter.training_probes != 4 || adapter.transfer_probes != 4)
            $fatal(1, "reused profile sent extra commands or probes");
        adapter.revision++;
        sqr.ctx.trace.delete();
        switch_bus(sqr);
        if (sqr.ctx.trace != first_trace || adapter.training_probes != 8 || adapter.transfer_probes != 8)
            $fatal(1, "changed revision reused stale taps");
        sqr.reset_phase(uvm_reset_phase::get());
        sqr.ctx.trace.delete();
        adapter.stall_probe = 1;
        fork
            switch_bus(sqr);
            begin
                wait (adapter.probe_running);
                switch_bus(sqr, HIGH_SPEED_SDR);
            end
        join
        if (sqr.ctx.trace != concurrent_trace ||
            adapter.training_probes != 12 || adapter.transfer_probes != 12)
            $fatal(1, "reset did not retune or another bus switch overlapped calibration: %p", sqr.ctx.trace);
        $display("AUTO_PHASE_PROBE_PASS");
        $finish;
    end
endmodule
