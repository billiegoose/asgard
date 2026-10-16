#include "Vstandalone_sim_top.h"
#include "verilated.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>

int main(int argc,char**argv) {
    if(argc!=4) return 2;
    std::ifstream input(argv[1],std::ios::binary);
    std::vector<unsigned char> image((std::istreambuf_iterator<char>(input)),{});
    std::string expected=argv[2],mode=argv[3],seen;
    Vstandalone_sim_top dut;
    size_t cursor=0;bool streaming=false;uint64_t last_clock=0;unsigned clocks=0;
    bool was_running=false;uint64_t run_cycles=0;unsigned pending_host=0;
    for(uint64_t cycle=0;cycle<100000000;cycle++) {
        dut.clk=0;dut.reset=cycle<8;dut.rx=1;
        if(mode=="rx" && was_running) {
            // A real 8N1 Z byte, delayed to allow the program to enter UART-RX.
            uint64_t t=run_cycles;
            if(t>=1000 && t<1040) {
                unsigned bit=(t-1000)/4;
                dut.rx=bit==0?0:bit==9?1:((90>>(bit-1))&1);
            }
        }
        dut.flash_valid=streaming && cursor<image.size();
        dut.flash_data=cursor<image.size()?image[cursor]:255;
        dut.eval();
        bool take=dut.flash_take;
        if(dut.flash_start) streaming=true;
        if(dut.flash_stop) streaming=false;
        if(dut.host_op) pending_host=dut.host_op;
        if(dut.resume_valid && pending_host==1) {
            if(dut.resume_data<last_clock || dut.resume_data>dut.milliseconds ||
               dut.milliseconds-dut.resume_data>1) {
                std::cerr<<"CLOCK mismatch\n";return 1;
            }
            last_clock=dut.resume_data;clocks++;
        }
        if(dut.resume_valid) pending_host=0;
        bool old_running=dut.running;
        dut.clk=1;dut.eval();
        if(take)cursor++;
        if(dut.running) {
            if(!old_running) {
                if(dut.milliseconds!=0) return 3;
                run_cycles=0;was_running=true;
            } else run_cycles++;
            // 100-cycle test divider; includes time waiting on UART.
            if(dut.milliseconds!=run_cycles/100) {
                std::cerr<<"elapsed counter mismatch "<<dut.milliseconds<<" "<<run_cycles<<"\n";return 1;
            }
        }
        if(dut.observed_valid) {
            seen.push_back(char(dut.observed_data));
            if(seen!=expected.substr(0,seen.size())) {std::cerr<<"UART mismatch\n";return 1;}
            if(seen==expected && mode=="stream") {
                std::cout<<"PASS UART="<<seen<<" cycles="<<cycle<<" CLOCK calls="<<clocks
                         <<" ms="<<dut.milliseconds<<" pc="<<dut.pc<<" fsp="<<dut.fsp<<"\n";
                return 0; // Stop explicitly after the requested output, not on timeout.
            }
        }
        if(cycle%1000000==0) std::cerr<<"progress cycle="<<cycle<<" flash="<<cursor<<" state="<<unsigned(dut.adapter_state)<<" status="<<unsigned(dut.status)<<" pc="<<dut.pc<<" micro="<<unsigned(dut.microstate)<<" ms="<<dut.milliseconds<<" UART="<<seen<<"\n";
        if(dut.fault) {
            if(mode=="corrupt" && !was_running) {std::cout<<"PASS rejected bad image fault="<<unsigned(dut.fault)<<"\n";return 0;}
            std::cerr<<"FAULT="<<unsigned(dut.fault)<<" core="<<unsigned(dut.red2_fault)
                     <<" micro="<<unsigned(dut.microstate)<<" pc="<<dut.pc<<" fsp="<<dut.fsp
                     <<" after UART="<<seen<<" cycle="<<cycle<<"\n";return 1;
        }
        if(dut.halted && mode!="stream") {
            if(seen!=expected) {std::cerr<<"halted before expected UART\n";return 1;}
            std::cout<<"PASS HALTED UART="<<seen<<" cycles="<<cycle<<" CLOCK calls="<<clocks<<"\n";return 0;
        }
    }
    std::cerr<<"FAIL finite cycle bound reached\n";return 1;
}
