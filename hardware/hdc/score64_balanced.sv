// F2 research-only alternative: identical score64 handshake and arithmetic.
// Explicit six-level pairwise reduction, no added pipeline latency.
// Transport still enforces packet order, dimension, and valid masks.
module score64_balanced(input logic clk, reset, input logic valid, output logic ready,
 input logic first, last, input logic [63:0] q,p,mask,
 output logic result_valid, input logic result_ready, output logic signed [31:0] result);
 function automatic [6:0] count64(input logic [63:0] bits);
  reg [1:0] s2 [0:31];
  reg [2:0] s4 [0:15];
  reg [3:0] s8 [0:7];
  reg [4:0] s16 [0:3];
  reg [5:0] s32 [0:1];
  integer i;
  begin
   for(i=0;i<32;i=i+1) s2[i]={1'b0,bits[2*i]}+{1'b0,bits[2*i+1]};
   for(i=0;i<16;i=i+1) s4[i]={1'b0,s2[2*i]}+{1'b0,s2[2*i+1]};
   for(i=0;i<8;i=i+1) s8[i]={1'b0,s4[2*i]}+{1'b0,s4[2*i+1]};
   for(i=0;i<4;i=i+1) s16[i]={1'b0,s8[2*i]}+{1'b0,s8[2*i+1]};
   for(i=0;i<2;i=i+1) s32[i]={1'b0,s16[2*i]}+{1'b0,s16[2*i+1]};
   count64={1'b0,s32[0]}+{1'b0,s32[1]};
  end
 endfunction
 logic [6:0] active,mismatch;
 logic signed [31:0] delta,accum,next_accum;
 assign active=count64(mask);
 assign mismatch=count64((q^p)&mask);
 assign delta=$signed({25'b0,active})-($signed({25'b0,mismatch})<<<1);
 assign next_accum=(first?32'sd0:accum)+delta;
 assign ready=~result_valid | result_ready;
 always_ff @(posedge clk) begin
  if(reset) begin accum<=0;result<=0;result_valid<=0;end
  else begin
   if(result_ready) result_valid<=0;
   if(valid && ready) begin
    accum<=next_accum;
    if(last) begin result<=next_accum;result_valid<=1;end
   end
  end
 end
endmodule
