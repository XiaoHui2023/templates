`timescale 1ns/1ps
`define uvm_object_utils(T)
`define uvm_fatal(ID, MSG) $fatal(1, MSG);
typedef enum {UVM_FRONTDOOR, UVM_BACKDOOR} uvm_path_e;
class uvm_callback;
    function new(string name = "");
    endfunction
endclass
class Emmc_ctrl_sequencer;
endclass

`include "core/clock_phase_types.sv"
`include "component/callback.sv"
`include "core/clock_phase_calibrator.sv"

module dw_emmc_clock_phase_probe;
    import Emmc_ctrl_clock_phase_types::*;

    class adapter extends Emmc_ctrl_callback;
        taps_t current = '{0, 0, 7};
        taps_t initial_taps = '{0, 0, 7};
        bit seen[int][int];
        int visits[int];
        int applies;
        string test_case;
        int previous_key = -1;

        function void clock_phase_describe(output axes_t axes);
            axes = '{
                '{"rx", 8, 5, 0},
                '{"tx", 8, 3, 0},
                '{"strobe", 2, 8, 1}
            };
            if (test_case == "bad_axis")
                axes[1].name = "rx";
            if (test_case == "empty_topology")
                axes.delete();
        endfunction

        task clock_phase_capture(output taps_t taps, output bit ok);
            taps = current;
            ok = 1;
        endtask

        task clock_phase_apply(input taps_t taps, output bit ok);
            applies++;
            current = taps;
            ok = 1;
            if (applies > 1 && taps == initial_taps) begin
                if (test_case == "restore_timeout")
                    #2us;
                if (test_case == "restore_fail")
                    ok = 0;
            end
            if (test_case == "apply_failed" && applies == 1)
                ok = 0;
        endtask

        task clock_phase_probe(input int group_id, output probe_e outcome);
            int key;

            visits[group_id]++;
            if (test_case == "timeout" && visits[group_id] == 2)
                #3us;
            if (test_case == "first_probe_timeout")
                #3us;
            if (test_case == "busy" && group_id == 8 && visits[group_id] == 1)
                #3ns;
            case (group_id)
                8: begin
                    key = current[0] + 5 * current[1];
                    if (seen[group_id].exists(key))
                        $fatal(1, "duplicate point in a coupled group");
                    seen[group_id][key] = 1;
                    if (previous_key >= 0 &&
                        !(key / 5 == previous_key / 5 &&
                          (key - previous_key == 1 || previous_key - key == 1)) &&
                        !(key - previous_key == 5 || previous_key - key == 5))
                        $fatal(1, "coupled sweep changed more than one axis");
                    previous_key = key;
                    outcome = (current[0] inside {[1:3]}) ? PROBE_PASSED : PROBE_REJECTED;
                    if (test_case inside {"no_window", "restore_fail", "restore_timeout"})
                        outcome = PROBE_REJECTED;
                end
                2: begin
                    key = current[2];
                    if (current[0] != 2 || current[1] != 1 || seen[group_id].exists(key))
                        $fatal(1, "independent sweep changed the chosen coupled taps");
                    seen[group_id][key] = 1;
                    outcome = (key inside {6, 7, 0, 1, 2}) ? PROBE_PASSED : PROBE_REJECTED;
                end
                CONFIRM_ALL_GROUPS:
                    outcome = test_case == "confirmation_fail" ? PROBE_REJECTED : PROBE_PASSED;
                default:
                    $fatal(1, "unexpected group");
            endcase
        endtask
    endclass

    initial begin
        Emmc_ctrl_clock_phase_calibrator calibrator;
        adapter stimulus;
        result_t result;
        taps_t expected;

        calibrator = new;
        stimulus = new;
        expected = '{2, 1, 0};
        if (!$value$plusargs("test=%s", stimulus.test_case))
            $fatal(1, "test name is required");
        case (stimulus.test_case)
            "no_adapter": begin
                calibrator.run(null, 25, 2, 2, 1, result);
                if (result.status != PHASE_SKIPPED || result.probes != 0)
                    $fatal(1, "null adapter must not do work");
            end
            "busy": begin
                fork
                    begin
                        calibrator.run(stimulus, 25, 2, 2, 1, result);
                        if (result.status != PHASE_PASSED)
                            $fatal(1, "first scan did not complete");
                    end
                    begin
                        result_t concurrent_call;

                        #1ns;
                        calibrator.run(stimulus, 25, 2, 2, 1, concurrent_call);
                        if (concurrent_call.status != PHASE_BUSY || concurrent_call.probes != 0)
                            $fatal(1, "overlapping scan was not rejected");
                    end
                join
            end
            "success": begin
                calibrator.run(stimulus, 25, 2, 2, 1, result);
                if (result.status != PHASE_PASSED || result.probes != 25 ||
                    stimulus.visits[8] != 15 || stimulus.visits[2] != 8 ||
                    stimulus.visits[CONFIRM_ALL_GROUPS] != 2 ||
                    result.selected != expected || stimulus.current != expected)
                    $fatal(1, "wrong selection, scan coverage, or final taps: %p", result);
            end
            default: begin
                status_e expected_status;
                case (stimulus.test_case)
                    "budget": expected_status = PHASE_BUDGET_EXCEEDED;
                    "bad_axis": expected_status = PHASE_BAD_TOPOLOGY;
                    "empty_topology": expected_status = PHASE_SKIPPED;
                    "apply_failed": expected_status = PHASE_ADAPTER_FAILED;
                    "no_window": expected_status = PHASE_NO_WINDOW;
                    "restore_fail", "restore_timeout": expected_status = PHASE_RESTORE_FAILED;
                    "confirmation_fail": expected_status = PHASE_CONFIRM_FAILED;
                    "timeout", "first_probe_timeout": expected_status = PHASE_TIMED_OUT;
                    default: $fatal(1, "invalid test");
                endcase
                calibrator.run(stimulus, stimulus.test_case == "budget" ? 24 : 25, 2, 2, 1, result);
                if (result.status != expected_status || result.selected.size() != 0 ||
                    stimulus.current != stimulus.initial_taps)
                    $fatal(1, "wrong error or rollback result: %p", result);
                if ((stimulus.test_case inside {"budget", "bad_axis", "empty_topology"}) && stimulus.applies != 0)
                    $fatal(1, "invalid plan wrote hardware");
                if (stimulus.test_case == "timeout" && stimulus.applies != 2)
                    $fatal(1, "timed-out scan did not restore a changed setting");
                if (stimulus.test_case == "first_probe_timeout" && stimulus.applies != 1)
                    $fatal(1, "timeout at the original tap did not invoke recovery");
                if ((stimulus.test_case inside {"restore_fail", "restore_timeout"}) &&
                    result.failure_before_restore != PHASE_NO_WINDOW)
                    $fatal(1, "restore failure lost the original failure");
            end
        endcase
        $display("PHASE_PROBE_PASS %s", stimulus.test_case);
        $finish;
    end
endmodule
