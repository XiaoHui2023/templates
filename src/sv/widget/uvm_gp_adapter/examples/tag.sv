class gp_example_tag extends uvm_tlm_extension #(gp_example_tag);
    int tag;

    // Allocate an independent extension.
    function new(string name = "gp_example_tag");
        super.new(name);
    endfunction
endclass
