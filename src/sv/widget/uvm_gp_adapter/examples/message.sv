class gp_example_message;
    bit [2:0] opcode;
    bit [12:0] address;
    bit [7:0] payload[$];
    int tag;
endclass
