
#include <cassert>
#include <fstream>
#include <iostream>
#include <iterator>
#include "soh/Network/Archipelago/TrackerMirror.h"
int main(int argc,char**argv){
 assert(argc==2);std::ifstream f(argv[1]);std::string payload((std::istreambuf_iterator<char>(f)),{});
 auto snapshot=SohExtreme::DecodeTrackerSnapshot(payload);assert(snapshot.version=="0.11.21");
 SohExtreme::TrackerMirrorState mirror;mirror.Reset(std::string(32,'1'));mirror.NextRequest();
 std::string status;assert(mirror.Accept(snapshot,1,10,status));
 auto current=mirror.Current(1,3,{100,101,102},{102},11,status);assert(current);
 assert(current->rows.size()==2 && current->rows[0].state==1 && current->rows[1].state==2);
 assert(current->rows[0].region=="Kokiri Forest" && current->rows[1].region=="Lake Hylia");
 snapshot.version="0.11.20";snapshot.revision++;assert(!mirror.Accept(snapshot,1,12,status));
 assert(!mirror.Current(1,4,{100,101,102},{102},12,status));
 std::cout<<"0.11.21 Python snapshot accepted by production C++ mirror; old version and mismatched receipts rejected\n";
}
