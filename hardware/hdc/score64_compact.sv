// F2B research: sum signed masked bipolar contributions with width-bounded tree.
// Each group of two samples contributes -2..2 (3 bits); each subsequent level
// adds one sign bit. Only the final running accumulator is 32 bits.
module score64_compact(input logic clk, reset, input logic valid, output logic ready,
 input logic first, last, input logic [63:0] q,p,mask,
 output logic result_valid, input logic result_ready, output logic signed [31:0] result);
 wire [63:0] mismatch=(q^p)&mask;
 wire signed [2:0] s2 [0:31];
 wire signed [3:0] s4 [0:15];
 wire signed [4:0] s8 [0:7];
 wire signed [5:0] s16 [0:3];
 wire signed [6:0] s32 [0:1];
 wire signed [7:0] delta;
 // A signed two-bit contribution is 00, 01 or 11. Both +/-1 have
 // low bit mask; sign bit mismatch. Extend *before* each addition.
 for(genvar i=0;i<32;i=i+1) begin: pairs
   wire signed [2:0] a=$signed({{2{mismatch[2*i]}},mask[2*i]});
   wire signed [2:0] b=$signed({{2{mismatch[2*i+1]}},mask[2*i+1]});
   assign s2[i]=a+b;
 end
 for(genvar i=0;i<16;i=i+1) begin: l4
   assign s4[i]=$signed({s2[2*i][2],s2[2*i]})+$signed({s2[2*i+1][2],s2[2*i+1]});
 end
 for(genvar i=0;i<8;i=i+1) begin: l8
   assign s8[i]=$signed({s4[2*i][3],s4[2*i]})+$signed({s4[2*i+1][3],s4[2*i+1]});
 end
 for(genvar i=0;i<4;i=i+1) begin: l16
   assign s16[i]=$signed({s8[2*i][4],s8[2*i]})+$signed({s8[2*i+1][4],s8[2*i+1]});
 end
 for(genvar i=0;i<2;i=i+1) begin: l32
   assign s32[i]=$signed({s16[2*i][5],s16[2*i]})+$signed({s16[2*i+1][5],s16[2*i+1]});
 end
 assign delta=$signed({s32[0][6],s32[0]})+$signed({s32[1][6],s32[1]});
 logic signed [31:0] accum,next_accum;
 assign next_accum=(first?32'sd0:accum)+$signed({{24{delta[7]}},delta});
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
