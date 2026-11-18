// Draft streaming score kernel only. Framing/CRC, PCIe and BRAM controller remain host/transport work.
module score64(input logic clk, reset, input logic valid, output logic ready,
 input logic first, last, input logic [63:0] q,p, mask,
 output logic result_valid, input logic result_ready, output logic signed [31:0] result);
 logic signed [31:0] accum,delta;
 integer j;
 always_comb begin
  delta=0;
  for(j=0;j<64;j=j+1) if(mask[j]) delta=delta+((q[j]==p[j])?32'sd1:-32'sd1);
 end
 assign ready=~result_valid | result_ready;
 always_ff @(posedge clk) begin
  if(reset) begin accum<=0;result<=0;result_valid<=0;end
  else begin
   if(result_ready) result_valid<=0;
   if(valid && ready) begin
    accum<=(first?32'sd0:accum)+delta;
    if(last) begin result<=(first?32'sd0:accum)+delta;result_valid<=1;end
   end
  end
 end
endmodule
