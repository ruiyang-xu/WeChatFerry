#pragma once

extern "C" {
__declspec(dllexport) int WxInitSDK(bool debug, int port);
// 按微信 ID（wxid）注入到指定的已登录微信进程。
// 传入 NULL 或空字符串时行为与 WxInitSDK 相同（自动选择第一个 WeChat.exe）。
__declspec(dllexport) int WxInitSDKEx(bool debug, int port, const char *wxid);
__declspec(dllexport) int WxDestroySDK();
}