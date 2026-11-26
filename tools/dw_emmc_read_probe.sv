`ifdef DW_EMMC_FACTORY_PROBE
`include "uvm_macros.svh"
`endif

module dw_emmc_read_probe;
`ifdef DW_EMMC_FACTORY_PROBE
    import uvm_pkg::*;
`endif
    class request;
        int block_count;
        bit rd_blocking;
        bit dma_enable;
    endclass

    class wait_sequence;
        int ready_count;
        task observe_ready();
            ready_count++;
        endtask
    endclass

`ifdef DW_EMMC_FACTORY_PROBE
`undef uvm_rand_send_with
`else
`define UVM_LOW 0
`define uvm_info(ID, MSG, LEVEL)
`endif
`define uvm_rand_send_with(SEQ, CONSTRAINTS) SEQ.observe_ready();

    class `PROBE_COMMAND_TYPE #(type CLASS_COMMAND_REQ = request)
`ifdef DW_EMMC_FACTORY_PROBE
        extends uvm_sequence
`endif
        ;
`ifdef DW_EMMC_FACTORY_PROBE
        `uvm_object_param_utils(`PROBE_COMMAND_TYPE#(CLASS_COMMAND_REQ))
        function new(string name = "command");
            super.new(name);
        endfunction

        task body();
            read(published);
        endtask
`endif
        CLASS_COMMAND_REQ cmd_request;
        wait_sequence wait_intr_seq = new;
        bit [7:0] published[$];
        int drained;
        int completions;
        bit dispatched;

        function wait_sequence create_wait_intr_seq();
            return wait_intr_seq;
        endfunction

`include "declarations.svh"
    endclass

`include "methods.svh"

    task `PROBE_COMMAND_TYPE::read_buffer_one_block(ref bit [7:0] data[$]);
`ifdef DW_EMMC_MOBILE_PROBE
        if (cmd_request.rd_blocking) begin
            if (completions != 1 || wait_intr_seq.ready_count != 0)
                $fatal(1, "mobile_storage blocked read needs DTO but not RXDR");
        end
        else
`endif
        if (wait_intr_seq.ready_count != drained + 1 || completions != 0)
            $fatal(1, "FIFO read without a new BRR");
        drained++;
        data.push_back(8'(drained));
    endtask

    task `PROBE_COMMAND_TYPE::wait_xfer_complete();
        bit wait_before_drain;

        wait_before_drain = cmd_request.dma_enable;
`ifdef DW_EMMC_MOBILE_PROBE
        wait_before_drain |= cmd_request.rd_blocking;
`endif
        completions++;
        if (wait_before_drain) begin
            if (drained != 0 || wait_intr_seq.ready_count != 0 || published.size() != 1)
                $fatal(1, "early data access on a completion-first path");
            return;
        end
        if (drained != cmd_request.block_count)
            $fatal(1, "TC before all blocks were drained");
        if (published.size() != (cmd_request.rd_blocking ? 1 : 1 + drained))
            $fatal(1, "incorrect payload visibility at TC: size=%0d", published.size());
    endtask

`ifdef DW_EMMC_DMA_PROBE
    task `PROBE_COMMAND_TYPE::read_memory(ref bit [7:0] data[$]);
        if (completions != 1 || drained != 0 || wait_intr_seq.ready_count != 0)
            $fatal(1, "DMA read must wait once without consuming FIFO data");
        for (int index = 1; index <= cmd_request.block_count; index++)
            data.push_back(8'(index));
    endtask
`endif

    class derived_request extends request;
    endclass

    typedef `PROBE_COMMAND_TYPE#(derived_request) operation_t;

    class derived_operation extends operation_t;
`ifdef DW_EMMC_FACTORY_PROBE
        `uvm_object_utils(derived_operation)
        function new(string name = "derived");
            super.new(name);
        endfunction
`endif
        task read(ref bit [7:0] data[$]);
            dispatched = 1;
            super.read(data);
        endtask
    endclass

    initial begin
        operation_t op;
        derived_operation derived;
        int blocks;

`ifdef DW_EMMC_FACTORY_PROBE
        begin
            typedef `PROBE_COMMAND_TYPE#(request) other_operation_t;
            other_operation_t other;

            operation_t::type_id::set_type_override(derived_operation::get_type());
            op = operation_t::type_id::create("command");
            if (!$cast(derived, op) || derived != op)
                $fatal(1, "exact request specialization did not create the override");
            other = other_operation_t::type_id::create("other");
            if (other.get_object_type() != other_operation_t::get_type())
                $fatal(1, "factory override leaked across request specializations");
            $display("FACTORY_PROBE_CREATED");
        end
`else
        derived = new;
        op = derived;
`endif
        op.cmd_request = new;
        if (!$value$plusargs("blocks=%d", blocks))
            $fatal(1, "missing block count");
        op.cmd_request.block_count = blocks;
        op.cmd_request.rd_blocking = $test$plusargs("blocking");
        op.cmd_request.dma_enable = $test$plusargs("dma");
        op.published.push_back(8'hfe);
`ifdef DW_EMMC_FACTORY_PROBE
        op.start(null);
`else
        op.read(op.published);
`endif
        if ($test$plusargs("dispatch") && !op.dispatched)
            $fatal(1, "derived method was not dispatched");
        if (op.completions != 1)
            $fatal(1, "one completion wait is required");
        if (op.published.size() != 1 + blocks || op.published[0] != 8'hfe)
            $fatal(1, "response size/prefix mismatch");
        for (int index = 1; index <= blocks; index++)
            if (op.published[index] != 8'(index))
                $fatal(1, "response ordering mismatch");
        $display("READ_PROBE_PASS");
        $finish;
    end
endmodule
