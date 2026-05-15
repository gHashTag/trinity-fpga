# Trinity FPGA — Root Makefile
# Wave-35 Lane W: LUT-NPU RTL targets
# R-SI-1: synth_check_no_star verifies zero star operators in lut_npu_controller.sv

# RTL source
LUT_NPU_RTL = rtl/lut_npu/lut_npu_controller.sv
LUT_NPU_TB  = tb/lut_npu/lut_npu_controller_tb.sv

.PHONY: synth_check_no_star sim_lut_npu help

# R-SI-1 compliance check: zero star operators in synthesizable RTL
synth_check_no_star:
	@count=$$(grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(LUT_NPU_RTL) | grep -v "^\s*//" | wc -l); \
	 if [ $$count -ne 0 ]; then \
	   echo "FAIL: $$count star op(s) in $(LUT_NPU_RTL)"; \
	   grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(LUT_NPU_RTL) | grep -v "^\s*//"; \
	   exit 1; \
	 fi; \
	 echo "R-SI-1 OK: zero star operators in $(LUT_NPU_RTL)"

# iverilog simulation target
sim_lut_npu:
	iverilog -g2001 -o /tmp/tb_lut_npu.vvp $(LUT_NPU_RTL) $(LUT_NPU_TB) && vvp /tmp/tb_lut_npu.vvp

help:
	@echo "Wave-35 Lane W — LUT-NPU RTL targets:"
	@echo "  make synth_check_no_star  -- R-SI-1: verify zero star ops"
	@echo "  make sim_lut_npu          -- run iverilog simulation"
