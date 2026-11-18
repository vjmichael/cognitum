# Vivado batch out-of-context lane benchmark. Not a board design.
# vivado -mode batch -source hardware/hdc/f2_vivado_ooc.tcl -tclargs score64 xc7k325tffg900-2 10.0 ./f2-vivado synth
if {$argc != 5} {error "args: top part period_ns output_directory synth|route"}
lassign $argv top part period out stage
if {$top ni {score64 score64_balanced score64_compact} || $stage ni {synth route}} {error "invalid top/stage"}
if {![regexp {^xc7k325t[a-z0-9]+-[123]$} $part]} {error "explicit provisional Kintex-7 XC7K325T part required"}
if {![string is double -strict $period] || $period < 2.0 || $period > 100.0} {error "period outside pilot range"}
set src [file join [file dirname [info script]] ${top}.sv]
file mkdir $out
set out [file normalize $out]
create_project -in_memory -part $part
read_verilog -sv $src
set xdc [file join $out lane.xdc]
set f [open $xdc w]
puts $f "create_clock -name lane_clk -period $period \[get_ports clk\]"
# All synchronous interface signals are assigned explicit illustrative OOC delays.
puts $f {set_input_delay -clock lane_clk -max 1.0 [get_ports {reset valid first last q[*] p[*] mask[*] result_ready}]}
puts $f {set_input_delay -clock lane_clk -min 0.0 [get_ports {reset valid first last q[*] p[*] mask[*] result_ready}]}
puts $f {set_output_delay -clock lane_clk -max 1.0 [get_ports {ready result_valid result[*]}]}
puts $f {set_output_delay -clock lane_clk -min 0.0 [get_ports {ready result_valid result[*]}]}
close $f
read_xdc $xdc
synth_design -top $top -part $part -mode out_of_context
report_utilization -file [file join $out synth_utilization.rpt]
report_timing_summary -report_unconstrained -file [file join $out synth_timing.rpt]
write_checkpoint -force [file join $out synth.dcp]
if {$stage eq "route"} {
 opt_design
 place_design
 route_design
 report_route_status -file [file join $out route_status.rpt]
 report_utilization -file [file join $out route_utilization.rpt]
 report_timing_summary -report_unconstrained -file [file join $out route_timing.rpt]
 report_drc -file [file join $out route_drc.rpt]
 write_checkpoint -force [file join $out route.dcp]
}
set setup [get_timing_paths -delay_type max -max_paths 1]
set hold [get_timing_paths -delay_type min -max_paths 1]
if {[llength $setup]!=1 || [llength $hold]!=1} {error "missing constrained timing path"}
set f [open [file join $out summary.tsv] w]
puts $f "top\t$top\npart\t$part\nperiod_ns\t$period\nstage\t$stage\nvivado\t[version -short]\nworst_setup_slack_ns\t[get_property SLACK $setup]\nworst_hold_slack_ns\t[get_property SLACK $hold]"
close $f
# Summary does not imply timing closure. Review timing coverage, route status and DRC.
