#include <array>
#include <map>
#include <vector>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <cerrno>
#include <sys/socket.h>
#include <netinet/in.h>
#include <poll.h>
#include <unistd.h>
#define private public
#include "GdbStub.h"
#undef private
#include "Platform.h"
static int zero_receives=0;
namespace melonDS::Platform {
void Log(LogLevel, const char* fmt, ...) {
 if (std::strcmp(fmt,"[GDB] receiving from stream %d\n")==0) {
  va_list ap; va_start(ap,fmt); if(va_arg(ap,int)==0) ++zero_receives; va_end(ap);
 }
}
}
int main(int argc, char** argv) {
 int pair[2]; if(socketpair(AF_UNIX,SOCK_STREAM,0,pair)) return 3;
 Gdb::GdbStub stub(nullptr); stub.ConnFd=pair[0];

 if(argc>1 && strcmp(argv[1], "--reconnect-mode")==0) {
  stub.NoAck=true;
  stub.RecvBufferFilled=3;
  stub.Disconnect();
  bool pass=!stub.NoAck && stub.RecvBufferFilled==0;
  printf("Reconnect starts in ACK mode with an empty receive buffer: %s\n",pass?"PASS":"FAIL");
  close(pair[1]); return pass?0:1;
 }

 if(argc>1 && strcmp(argv[1], "--handshake-failure")==0) {
  stub.Disconnect(); close(pair[1]);
  stub.SockFd=socket(AF_INET, SOCK_STREAM, 0);
  sockaddr_in addr{}; addr.sin_family=AF_INET; addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
  if(stub.SockFd<0 || bind(stub.SockFd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr))
     || listen(stub.SockFd, 1)) return 9;
  socklen_t len=sizeof(addr);
  if(getsockname(stub.SockFd, reinterpret_cast<sockaddr*>(&addr), &len)) return 10;
  int peer=socket(AF_INET, SOCK_STREAM, 0);
  if(peer<0 || connect(peer, reinterpret_cast<sockaddr*>(&addr), sizeof(addr))) return 11;
  if(shutdown(peer, SHUT_WR)) return 12;
  // Seed state directly to test the failed-handshake cleanup contract in isolation.
  stub.AddBkpt(0x02001234, 0); stub.AddWatchpt(0x02005678, 4, 2);
  auto state=stub.Poll(false);
  bool pass=state==Gdb::StubState::Disconnect && !stub.IsConnected()
   && stub.BpList.empty() && stub.WpList.empty();
  printf("Failed handshake clears breakpoint/watchpoint state: %s\n",pass?"PASS":"FAIL");
  close(peer); return pass?0:1;
 }
 bool idle_ok=stub.Poll(false)==Gdb::StubState::None && stub.MsgRecv()==Gdb::ReadResult::NoPacket;
 unsigned char interrupt=3; if(send(pair[1],&interrupt,1,0)!=1) return 5;
 bool break_ok=stub.Poll(false)==Gdb::StubState::Break;
 printf("open idle/EAGAIN: %s; interrupt packet: %s\n",idle_ok?"PASS":"FAIL",break_ok?"PASS":"FAIL");
 if(argc>1 && strcmp(argv[1], "--idle")==0) return idle_ok?0:1;
 if(argc>1 && strcmp(argv[1], "--interrupt")==0) return break_ok?0:1;
 if(argc>1 && strncmp(argv[1], "--stale-", 8)==0) {
  stub.AddBkpt(0x02001234, 0);
  stub.AddWatchpt(0x02005678, 4, 2);
  if(strcmp(argv[1], "--stale-eof")==0) {
   shutdown(pair[1], SHUT_WR);
   if(stub.Enter(true)!=Gdb::StubState::Disconnect) return 6;
  } else if(strcmp(argv[1], "--stale-hup")==0) {
   close(pair[1]); pair[1]=-1;
   if(stub.Enter(true)!=Gdb::StubState::Disconnect) return 7;
  } else if(strcmp(argv[1], "--stale-detach")==0) {
   stub.NoAck=true; stub.Cmdbuf[0]='D'; stub.Cmdlen=1;
   if(stub.HandlePacket()!=Gdb::StubState::Disconnect) return 8;
  } else {
   stub.Disconnect();
  }
  std::fflush(stdout);
  bool pass=stub.CheckBkpt(0x02001234, true, true)==Gdb::StubState::CheckNoHit
   && stub.CheckWatchpt(0x02005678, 2, true, true)==Gdb::StubState::CheckNoHit
   && stub.BpList.empty() && stub.WpList.empty() && !stub.IsConnected();
  printf("Disconnected breakpoint/watchpoint hit returns: %s\n",pass?"PASS":"FAIL");
  if(pair[1]>=0) close(pair[1]);
  return pass?0:1;
 }
 if(shutdown(pair[1],SHUT_WR)) return 4;
 pollfd pfd{pair[0],POLLIN,0}; poll(&pfd,1,0);
 printf("half-closed peer: poll.revents=%d POLLIN=%d POLLHUP=%d\n",pfd.revents,POLLIN,POLLHUP);
 if(argc>1 && strcmp(argv[1], "--enter")==0) {
  std::fflush(stdout);
  auto state=stub.Enter(true);
  bool pass=state==Gdb::StubState::Disconnect && !stub.IsConnected();
  printf("Enter(true) returns on EOF: %s\n",pass?"PASS":"FAIL");
  close(pair[1]); return pass?0:1;
 }
 int idle=0, disconnected=0;
 for(int i=0;i<100;i++) {
  auto state=stub.Poll(false);
  if(state==Gdb::StubState::None) ++idle;
  if(state==Gdb::StubState::Disconnect) { ++disconnected; break; }
 }
 printf("polls: idle=%d disconnect=%d recv_zero=%d connected=%d\n",idle,disconnected,zero_receives,stub.IsConnected());
 bool pass=idle_ok && break_ok && (pfd.revents & POLLIN) && !(pfd.revents & POLLHUP) && disconnected==1 && !stub.IsConnected();
 printf("EOF disconnect invariant: %s\n",pass?"PASS":"FAIL");
 close(pair[1]); return pass?0:1;
}
