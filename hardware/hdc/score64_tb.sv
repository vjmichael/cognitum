// Independently generated per-cycle expected values; ready/valid, stalls,
// simultaneous retirement/acceptance, reset-mid-frame, tails, max length.
module score64_tb;
 logic clk=0,reset=1,valid=0,ready,first=0,last=0,result_valid,result_ready=0;
 logic [63:0] q=0,p=0,mask=0;
 logic signed [31:0] result;
 score64 dut(.*);
 always #5 clk=~clk;
 integer f,n,cycle,er,ev,rr,rv,rst,v,fi,la;
 logic signed [31:0] expected_before,expected_after;
 string vector_path;
 initial begin
  if(!$value$plusargs("vectors=%s",vector_path))$fatal(1,"vector path required");
  f=$fopen(vector_path,"r");if(!f)$fatal(1,"vector open");
  repeat(2) @(posedge clk);
  cycle=0;
  while(!$feof(f))begin
   @(negedge clk);
   n=$fscanf(f,"%d %d %d %d %d %h %h %h %d %d %h %d %h\n",rst,v,fi,la,rr,q,p,mask,er,ev,expected_before,rv,expected_after);
   if(n==13)begin
    reset=rst;valid=v;first=fi;last=la;result_ready=rr;
    #1;if(ready!==er[0]||result_valid!==ev[0]||(ev&&result!==expected_before))$fatal(1,"before cycle %d",cycle);
    @(posedge clk);#1;
    if(result_valid!==rv[0]||(rv&&result!==expected_after))$fatal(1,"after cycle %d",cycle);
    cycle=cycle+1;
   end else if(n!=-1)$fatal(1,"malformed vector record");
  end
  $fclose(f);if(cycle<2000)$fatal(1,"insufficient vectors");
  $display("PASS score64 %0d cycles",cycle);$finish;
 end
 initial begin #1000000;$fatal(1,"timeout");end
endmodule
