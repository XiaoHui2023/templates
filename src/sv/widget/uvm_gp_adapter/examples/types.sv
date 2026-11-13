class gp_example_types;
    typedef struct {
        bit [63:0] addr;
        bit is_write;
        uvm_tlm_response_status_e status;
        int beat_bytes;
        bit [15:0] words[$];
        bit [7:0] enables[$];
    } packet_t;

    typedef struct packed {
        bit [12:0] data;
    } packed_t;

    typedef struct {
        bit [31:0] data[2];
    } fixed_t;

    typedef struct {
        bit [23:0] data[];
    } dynamic_t;

    typedef struct {
        int count;
        int valid_bytes;
        bit [7:0] data[$];
    } prefix_t;
endclass
