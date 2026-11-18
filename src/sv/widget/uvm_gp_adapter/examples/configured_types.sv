class gp_config_types;
    typedef struct {
        bit [63:0] address;
        uvm_tlm_command_e command;
        uvm_tlm_response_status_e status;
        int count;
        int beat_elements;
        int raw_length;
        int mask_length;
        bit [15:0] words[$];
        bit [3:0] strobes;
        bit [7:0] mask[$];
    } transaction_t;
    typedef struct packed {
        bit [2:0] opcode;
        bit [12:0] address;
    } header_t;
endclass
