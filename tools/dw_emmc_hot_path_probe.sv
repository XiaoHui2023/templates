`define uvm_object_utils(T)
`define uvm_info(ID, MESSAGE, LEVEL)
`define uvm_error(ID, MESSAGE) $fatal(1, "%s: %s", ID, MESSAGE);

class Emmc_ctrl_base_object;
    function new(string name);
    endfunction
endclass

`include "core/mem.sv"

class fifo_model;
    int words;

    task read(output bit status, output bit [31:0] word_data);
        word_data = 32'h0403_0201 + words * 32'h0404_0404;
        words++;
        status = 1;
    endtask
endclass

class regs;
    fifo_model BUF_DATA_R = new;
endclass

class request;
    int block_size;
endclass

class Emmc_ctrl_command_operation_seq;
    regs rm = new;
    request cmd_request = new;
    bit status;

    extern task read_buffer_one_block(ref bit [7:0] data[$]);
endclass

`include "fifo_read.svh"

module dw_emmc_hot_path_probe;
    initial begin
        Emmc_ctrl_mem model = new;
        Emmc_ctrl_command_operation_seq command_seq = new;
        bit [7:0] payload[$] = '{8'h11, 8'h22, 8'h33};
        bit [7:0] with_gap[$] = '{8'h00, 8'h11, 8'h22, 8'h33};
        bit [7:0] actual[$];
        bit [7:0] expected[$] = '{8'h7f, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
        string message;
        localparam longint BOOT_BASE = 64'h1_0000_0000;

        if (!$test$plusargs("dense_only")) begin
            model.write(BOOT_BASE, payload);
            if (!model.read(BOOT_BASE - 1, 4, actual, message) ||
                actual != with_gap)
                $fatal(1, "high byte address or zero gap changed");
            if (model.read(BOOT_BASE + 3, 1, actual, message))
                $fatal(1, "out-of-range read succeeded");
        end

        model.clear();
        model.write(7, payload);
        if (!model.read(6, 4, actual, message) || actual != with_gap)
            $fatal(1, "dense write or zero gap changed");
        model.clear();
        if (model.read(7, 1, actual, message))
            $fatal(1, "clear left stale data");

        actual = '{8'h7f};
        command_seq.cmd_request.block_size = 4;
        command_seq.read_buffer_one_block(actual);
        command_seq.cmd_request.block_size = 6;
        command_seq.read_buffer_one_block(actual);
        if (actual != expected || command_seq.rm.BUF_DATA_R.words != 3)
            $fatal(1, "FIFO changed byte order, existing prefix or final partial word");
        $display("HOT_PATH_PROBE_PASS");
        $finish;
    end
endmodule
