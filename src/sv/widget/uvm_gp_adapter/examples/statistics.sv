module gp_adapter_statistics_usage;
    import uvm_pkg::*;
    packet_gp_adapter adapter;

    initial begin
        gp_example_types::packet_t packet, restored;
        packet_gp_adapter::statistics_t snapshot;
        uvm_tlm_generic_payload gp;
        adapter = new("statistics_adapter",null);
        packet.words = '{16'h1234,16'habcd};
        packet.enables = '{8'hff,8'h00};
        packet.is_write = 1;
        packet.beat_bytes = 2;
        packet.status = UVM_TLM_OK_RESPONSE;
        adapter.clear_statistics();
        if (!adapter.to_gp(packet,gp)) $fatal(1,"%s",adapter.last_error);
        if (!adapter.from_gp(gp,restored)) $fatal(1,"%s",adapter.last_error);
        adapter.get_statistics(snapshot);
        $display("to_gp: success=%0d failure=%0d bytes=%0d",
            snapshot.to_gp.success_count,snapshot.to_gp.failure_count,snapshot.to_gp.success_bytes);
        $display("from_gp: success=%0d failure=%0d bytes=%0d",
            snapshot.from_gp.success_count,snapshot.from_gp.failure_count,snapshot.from_gp.success_bytes);
        // Count valid data bytes, including disabled bytes, after all steps succeed.
        if (snapshot.to_gp.success_bytes != 4 || snapshot.from_gp.success_bytes != 4)
            $fatal(1,"unexpected statistics");
        adapter.clear_statistics();
        adapter.get_statistics(snapshot);
        if (snapshot != '0) $fatal(1,"clear failed");
        // reset_phase clears the same counters during the UVM reset schedule.
    end
endmodule
