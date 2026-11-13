module gp_adapter_usage;
    import uvm_pkg::*;

    packet_gp_adapter packet_adapter;
    message_gp_adapter message_adapter;

    initial begin
        gp_example_types::packet_t packet, restored_packet;
        gp_example_message message, restored_message;
        uvm_tlm_generic_payload gp;

        packet_adapter = new("packet_adapter", null);
        message_adapter = new("message_adapter", null);
        packet.addr = 64'h1000;
        packet.is_write = 1;
        packet.status = UVM_TLM_INCOMPLETE_RESPONSE;
        packet.beat_bytes = 2;
        packet.words = '{16'h1234, 16'habcd};
        packet.enables = '{8'hff, 8'h00};
        if (!packet_adapter.to_gp(packet, gp))
            $fatal(1, "%s", packet_adapter.last_error);
        if (!packet_adapter.from_gp(gp, restored_packet))
            $fatal(1, "%s", packet_adapter.last_error);

        message = new();
        message.opcode = 5;
        message.address = 13'h1abc;
        message.payload = '{8'h91, 8'hff};
        message.tag = 837;
        if (!message_adapter.to_gp(message, gp))
            $fatal(1, "%s", message_adapter.last_error);
        if (!message_adapter.from_gp(gp, restored_message))
            $fatal(1, "%s", message_adapter.last_error);
    end
endmodule
