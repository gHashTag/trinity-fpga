# Trinity FPGA — Root Makefile
# Wave-35 Lane W: LUT-NPU RTL targets
# Wave-36 Lane Y: AVS-48 RTL targets
# R-SI-1: synth_check_no_star verifies zero star operators in RTL

# RTL source
LUT_NPU_RTL = rtl/lut_npu/lut_npu_controller.sv
LUT_NPU_TB  = tb/lut_npu/lut_npu_controller_tb.sv

# AVS-48 RTL source (Wave-36 Lane Y)
AVS_RTL = rtl/avs/avs_regulator.sv
AVS_TB  = tb/avs/avs_regulator_tb.sv

.PHONY: synth_check_no_star sim_lut_npu synth_check_no_star_avs sim_avs help

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

# R-SI-1 compliance check for AVS RTL
synth_check_no_star_avs:
	@count=$$(grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(AVS_RTL) | grep -v "^\s*//" | wc -l); \
	 if [ $$count -ne 0 ]; then \
	   echo "FAIL: $$count star op(s) in $(AVS_RTL)"; \
	   grep -E '[^a-zA-Z_]\*[^a-zA-Z_/]' $(AVS_RTL) | grep -v "^\s*//"; \
	   exit 1; \
	 fi; \
	 echo "R-SI-1 OK: zero star operators in $(AVS_RTL)"

# iverilog simulation for AVS-48 (Wave-36 Lane Y)
sim_avs:
	iverilog -g2012 -o /tmp/tb_avs.vvp $(AVS_RTL) $(AVS_TB) && vvp /tmp/tb_avs.vvp

help:
	@echo "Wave-35 Lane W — LUT-NPU RTL targets:"
	@echo "  make synth_check_no_star      -- R-SI-1: verify zero star ops (LUT-NPU)"
	@echo "  make sim_lut_npu              -- run iverilog simulation (LUT-NPU)"
	@echo "Wave-36 Lane Y — AVS-48 RTL targets:"
	@echo "  make synth_check_no_star_avs  -- R-SI-1: verify zero star ops (AVS)"
	@echo "  make sim_avs                  -- run iverilog simulation (AVS-48)"
