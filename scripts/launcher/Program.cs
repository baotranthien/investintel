using System;
using System.Diagnostics;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace InvestIntelLauncher
{
    class Program
    {
        #region Win32 Job Object (Ensures 100% child process cleanup on exit)
        [DllImport("kernel32.dll", CharSet = CharSet.Auto)]
        static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string lpName);

        [DllImport("kernel32.dll")]
        static extern bool SetInformationJobObject(IntPtr hJob, int infoType, IntPtr lpJobObjectInfo, uint cbJobObjectInfoLength);

        [DllImport("kernel32.dll")]
        static extern bool AssignProcessToJobObject(IntPtr hJob, IntPtr hProcess);

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern bool CloseHandle(IntPtr hObject);

        [StructLayout(LayoutKind.Sequential)]
        struct IO_COUNTERS
        {
            public ulong ReadOperationCount;
            public ulong WriteOperationCount;
            public ulong OtherOperationCount;
            public ulong ReadTransferCount;
            public ulong WriteTransferCount;
            public ulong OtherTransferCount;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_BASIC_LIMIT_INFORMATION
        {
            public long PerProcessUserTimeLimit;
            public long PerJobUserTimeLimit;
            public uint LimitFlags;
            public UIntPtr MinimumWorkingSetSize;
            public UIntPtr MaximumWorkingSetSize;
            public uint ActiveProcessLimit;
            public UIntPtr Affinity;
            public uint PriorityClass;
            public uint SchedulingClass;
        }

        [StructLayout(LayoutKind.Sequential)]
        struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
        {
            public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
            public IO_COUNTERS IoInfo;
            public UIntPtr ProcessMemoryLimit;
            public UIntPtr JobMemoryLimit;
            public UIntPtr PeakProcessMemoryLimit;
            public UIntPtr PeakJobMemoryLimit;
        }

        const int JobObjectExtendedLimitInformation = 9;
        const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000;
        static IntPtr s_jobHandle = IntPtr.Zero;

        static void InitJobObject()
        {
            try
            {
                s_jobHandle = CreateJobObject(IntPtr.Zero, null);
                if (s_jobHandle != IntPtr.Zero)
                {
                    JOBOBJECT_EXTENDED_LIMIT_INFORMATION info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
                    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

                    int length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
                    IntPtr extendedInfoPtr = Marshal.AllocHGlobal(length);
                    try
                    {
                        Marshal.StructureToPtr(info, extendedInfoPtr, false);
                        SetInformationJobObject(s_jobHandle, JobObjectExtendedLimitInformation, extendedInfoPtr, (uint)length);
                    }
                    finally
                    {
                        Marshal.FreeHGlobal(extendedInfoPtr);
                    }
                }
            }
            catch { }
        }

        static void BindToJob(Process proc)
        {
            try
            {
                if (s_jobHandle != IntPtr.Zero && proc != null && !proc.HasExited)
                {
                    AssignProcessToJobObject(s_jobHandle, proc.Handle);
                }
            }
            catch { }
        }
        #endregion

        static Process s_backendProcess = null;
        static Process s_frontendProcess = null;
        static Process s_ollamaProcess = null;
        static bool s_isShuttingDown = false;
        static readonly object s_lock = new object();

        static int Main(string[] args)
        {
            try
            {
                Console.OutputEncoding = Encoding.UTF8;
            }
            catch { }

            InitJobObject();

            try { Console.Title = "InvestIntel Terminal — Unified Launcher"; } catch { }
            try { Console.Clear(); } catch { }
            PrintBanner();

            string projectRoot = DetectProjectRoot();
            if (string.IsNullOrEmpty(projectRoot))
            {
                PrintColor("[LỖI] Không tìm thấy thư mục gốc của InvestIntel (thiếu .venv hoặc apps\\web).", ConsoleColor.Red);
                PrintColor("Vui lòng đặt file InvestIntel.exe tại thư mục dự án.", ConsoleColor.Yellow);
                Console.WriteLine("\nNhấn phím bất kỳ để thoát...");
                Console.ReadKey();
                return 1;
            }

            if (args.Length > 0 && args[0] == "--test")
            {
                PrintColor("[TEST PASS] InvestIntel.exe binary test mode OK.", ConsoleColor.Green);
                PrintColor(string.Format("Project root: {0}", projectRoot), ConsoleColor.DarkGray);
                PrintColor(string.Format("Python virtualenv: {0}", File.Exists(Path.Combine(projectRoot, ".venv", "Scripts", "python.exe"))), ConsoleColor.DarkGray);
                PrintColor(string.Format("Next.js frontend: {0}", Directory.Exists(Path.Combine(projectRoot, "apps", "web"))), ConsoleColor.DarkGray);
                return 0;
            }

            PrintColor(string.Format("[*] Thư mục dự án: {0}", projectRoot), ConsoleColor.DarkGray);

            // Register Shutdown hooks
            Console.CancelKeyPress += (sender, e) =>
            {
                e.Cancel = true;
                ShutdownAll("Ctrl+C");
            };
            AppDomain.CurrentDomain.ProcessExit += (sender, e) =>
            {
                ShutdownAll("ProcessExit");
            };

            // 1. Dọn dẹp các tiến trình treo trên cổng 8000 và 3000 nếu có
            PrintColor("[*] Kiểm tra và giải phóng cổng mạng (8000, 3000)...", ConsoleColor.Cyan);
            FreePortIfOccupied(8000);
            FreePortIfOccupied(3000);

            // 2. Khởi động Ollama (nếu có trên máy và chưa chạy)
            TryStartOllama(projectRoot);

            // 3. Khởi động FastAPI Backend
            PrintColor("\n[1/2] Đang khởi chạy FastAPI Backend (Port 8000)...", ConsoleColor.Yellow);
            if (!StartBackend(projectRoot))
            {
                PrintColor("[LỖI] Không thể khởi động Backend.", ConsoleColor.Red);
                ShutdownAll("BackendStartFailed");
                return 1;
            }

            // 4. Khởi động Next.js Frontend
            PrintColor("[2/2] Đang khởi chạy Next.js Frontend (Port 3000)...", ConsoleColor.Yellow);
            if (!StartFrontend(projectRoot))
            {
                PrintColor("[LỖI] Không thể khởi động Frontend.", ConsoleColor.Red);
                ShutdownAll("FrontendStartFailed");
                return 1;
            }

            // 5. Chờ cả 2 dịch vụ sẵn sàng
            PrintColor("\n[*] Đang xác nhận kết nối hệ thống (Health Check)...", ConsoleColor.Cyan);
            bool backendReady = WaitForEndpoint("http://127.0.0.1:8000/health", 45, "Backend (8000)");
            bool frontendReady = WaitForEndpoint("http://localhost:3000", 45, "Frontend (3000)");

            if (!backendReady || !frontendReady)
            {
                PrintColor("\n[CẢNH BÁO] Một số dịch vụ mất nhiều thời gian hơn dự kiến để khởi động.", ConsoleColor.Yellow);
            }
            else
            {
                PrintColor("\n╔══════════════════════════════════════════════════════════════════╗", ConsoleColor.Green);
                PrintColor("║             INVESTINTEL SYSTEM IS FULLY OPERATIONAL              ║", ConsoleColor.Green);
                PrintColor("╚══════════════════════════════════════════════════════════════════╝", ConsoleColor.Green);
                PrintColor("[OK] FastAPI Backend:   http://127.0.0.1:8000/docs", ConsoleColor.White);
                PrintColor("[OK] Next.js Terminal:  http://localhost:3000", ConsoleColor.White);
            }

            // 6. Tự động mở trình duyệt web
            PrintColor("\n[>>] Đang tự động mở trình duyệt đến http://localhost:3000 ...", ConsoleColor.Green);
            try
            {
                Process.Start(new ProcessStartInfo("http://localhost:3000") { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                PrintColor(string.Format("[!] Không thể tự mở trình duyệt: {0}. Vui lòng mở thủ công http://localhost:3000", ex.Message), ConsoleColor.DarkYellow);
            }

            // 7. Interactive Monitor loop
            PrintDashboardControls();

            while (!s_isShuttingDown)
            {
                try
                {
                    if (Console.KeyAvailable)
                    {
                        ConsoleKeyInfo key = Console.ReadKey(true);
                        if (key.Key == ConsoleKey.Q || (key.Modifiers.HasFlag(ConsoleModifiers.Control) && key.Key == ConsoleKey.C))
                        {
                            ShutdownAll("UserRequested");
                            break;
                        }
                        else if (key.Key == ConsoleKey.B)
                        {
                            PrintColor("[>>] Mở lại trình duyệt...", ConsoleColor.Cyan);
                            try { Process.Start(new ProcessStartInfo("http://localhost:3000") { UseShellExecute = true }); } catch { }
                        }
                        else if (key.Key == ConsoleKey.R)
                        {
                            try { Console.Clear(); } catch { }
                            PrintBanner();
                            PrintColor(string.Format("[*] Thư mục dự án: {0}", projectRoot), ConsoleColor.DarkGray);
                            PrintColor("[OK] FastAPI Backend:   http://127.0.0.1:8000", ConsoleColor.Green);
                            PrintColor("[OK] Next.js Terminal:  http://localhost:3000", ConsoleColor.Green);
                            PrintDashboardControls();
                        }
                    }
                }
                catch (InvalidOperationException)
                {
                    // Non-interactive console / redirected input, just wait
                    Thread.Sleep(1000);
                    continue;
                }
                Thread.Sleep(200);
            }

            return 0;
        }

        static void PrintBanner()
        {
            PrintColor("  ██╗███╗   ██╗██╗   ██╗███████╗███████╗████████╗██╗███╗   ██╗████████╗███████╗██╗     ", ConsoleColor.Cyan);
            PrintColor("  ██║████╗  ██║██║   ██║██╔════╝██╔════╝╚══██╔══╝██║████╗  ██║╚══██╔══╝██╔════╝██║     ", ConsoleColor.Cyan);
            PrintColor("  ██║██╔██╗ ██║██║   ██║█████╗  ███████╗   ██║   ██║██╔██╗ ██║   ██║   █████╗  ██║     ", ConsoleColor.Cyan);
            PrintColor("  ██║██║╚██╗██║╚██╗ ██╔╝██╔══╝  ╚════██║   ██║   ██║██║╚██╗██║   ██║   ██╔══╝  ██║     ", ConsoleColor.Cyan);
            PrintColor("  ██║██║ ╚████║ ╚████╔╝ ███████╗███████║   ██║   ██║██║ ╚████║   ██║   ███████╗███████╗", ConsoleColor.Cyan);
            PrintColor("  ╚═╝╚═╝  ╚═══╝  ╚═══╝  ╚══════╝╚══════╝   ╚═╝   ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚══════╝", ConsoleColor.Cyan);
            PrintColor("                 VIETNAM FINANCIAL RESEARCH WORKSTATION · 1-CLICK LAUNCHER              \n", ConsoleColor.DarkCyan);
        }

        static void PrintDashboardControls()
        {
            Console.WriteLine();
            PrintColor("──────────────────────────────────────────────────────────────────", ConsoleColor.DarkGray);
            PrintColor("  [B] Mở lại trình duyệt   |   [R] Làm mới màn hình   |   [Q] Thoát", ConsoleColor.White);
            PrintColor("──────────────────────────────────────────────────────────────────", ConsoleColor.DarkGray);
            PrintColor("Hệ thống đang chạy nền. Giữ cửa sổ này mở trong khi sử dụng.", ConsoleColor.DarkGray);
        }

        static string DetectProjectRoot()
        {
            string[] candidates = new string[]
            {
                AppDomain.CurrentDomain.BaseDirectory,
                Directory.GetCurrentDirectory(),
                Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "..")),
                @"C:\Users\baotr\Downloads\trading"
            };

            foreach (string dir in candidates)
            {
                if (Directory.Exists(dir))
                {
                    string venvPython = Path.Combine(dir, ".venv", "Scripts", "python.exe");
                    string appsWeb = Path.Combine(dir, "apps", "web");
                    if (File.Exists(venvPython) && Directory.Exists(appsWeb))
                    {
                        return Path.GetFullPath(dir);
                    }
                }
            }
            return null;
        }

        static void FreePortIfOccupied(int port)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("netstat", "-ano -p tcp")
                {
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    CreateNoWindow = true
                };

                using (Process p = Process.Start(psi))
                {
                    string output = p.StandardOutput.ReadToEnd();
                    p.WaitForExit();

                    string match = string.Format(":{0} ", port);
                    foreach (string line in output.Split('\n'))
                    {
                        if (line.Contains(match) && line.Contains("LISTENING"))
                        {
                            string[] tokens = line.Trim().Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
                            if (tokens.Length >= 5)
                            {
                                int pid;
                                if (int.TryParse(tokens[tokens.Length - 1], out pid) && pid > 0 && pid != Process.GetCurrentProcess().Id)
                                {
                                    PrintColor(string.Format("    -> Đang giải phóng tiến trình cũ (PID {0}) đang giữ cổng {1}...", pid, port), ConsoleColor.DarkYellow);
                                    try
                                    {
                                        Process kp = Process.Start(new ProcessStartInfo("taskkill", string.Format("/F /T /PID {0}", pid))
                                        {
                                            CreateNoWindow = true,
                                            UseShellExecute = false
                                        });
                                        if (kp != null) kp.WaitForExit();
                                    }
                                    catch { }
                                }
                            }
                        }
                    }
                }
            }
            catch { }
        }

        static void WritePidFile(string projectRoot, string fileName, int pid)
        {
            try
            {
                string runDir = Path.Combine(projectRoot, ".run");
                if (!Directory.Exists(runDir)) Directory.CreateDirectory(runDir);
                File.WriteAllText(Path.Combine(runDir, fileName), pid.ToString());
            }
            catch { }
        }

        static void CleanPidFiles(string projectRoot)
        {
            try
            {
                if (string.IsNullOrEmpty(projectRoot)) projectRoot = DetectProjectRoot();
                if (string.IsNullOrEmpty(projectRoot)) return;
                string runDir = Path.Combine(projectRoot, ".run");
                if (Directory.Exists(runDir))
                {
                    foreach (string f in Directory.GetFiles(runDir, "*.pid"))
                    {
                        try { File.Delete(f); } catch { }
                    }
                }
            }
            catch { }
        }

        static void WriteSupervisorLog(string projectRoot, string level, string message)
        {
            try
            {
                string logDir = Path.Combine(projectRoot, "logs", "supervisor");
                if (!Directory.Exists(logDir)) Directory.CreateDirectory(logDir);
                string logPath = Path.Combine(logDir, "supervisor.log");
                string line = string.Format("[{0}] [{1}] {2}{3}", DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"), level, message, Environment.NewLine);
                File.AppendAllText(logPath, line, Encoding.UTF8);
            }
            catch { }
        }

        static string ResolveOllamaPath()
        {
            string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string[] ollamaPaths = new string[]
            {
                @"C:\Users\baotr\AppData\Local\Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe",
                Path.Combine(localAppData, @"Microsoft\WinGet\Packages\Ollama.Ollama.Portable_Microsoft.Winget.Source_8wekyb3d8bbwe\ollama.exe"),
                @"C:\Users\baotr\AppData\Local\Programs\Ollama\ollama.exe",
                Path.Combine(localAppData, @"Programs\Ollama\ollama.exe")
            };

            foreach (string p in ollamaPaths)
            {
                if (File.Exists(p)) return p;
            }

            try
            {
                string wingetDir = Path.Combine(localAppData, @"Microsoft\WinGet\Packages");
                if (Directory.Exists(wingetDir))
                {
                    string[] dirs = Directory.GetDirectories(wingetDir, "Ollama*");
                    foreach (string d in dirs)
                    {
                        string candidate = Path.Combine(d, "ollama.exe");
                        if (File.Exists(candidate)) return candidate;
                    }
                }
            }
            catch { }

            try
            {
                string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
                foreach (string dir in pathEnv.Split(';'))
                {
                    if (!string.IsNullOrEmpty(dir))
                    {
                        string candidate = Path.Combine(dir.Trim(), "ollama.exe");
                        if (File.Exists(candidate)) return candidate;
                    }
                }
            }
            catch { }

            return null;
        }

        static void TryStartOllama(string projectRoot)
        {
            try
            {
                // Check if already running on 11434
                if (IsPortListening(11434))
                {
                    PrintColor("[OK] Ollama server đã sẵn sàng tại port 11434.", ConsoleColor.DarkGreen);
                    WriteSupervisorLog(projectRoot, "OK", "Ollama is already running on port 11434.");
                    return;
                }

                string foundOllama = ResolveOllamaPath();
                if (!string.IsNullOrEmpty(foundOllama))
                {
                    PrintColor("[*] Đang khởi động dịch vụ Ollama cục bộ...", ConsoleColor.Cyan);
                    ProcessStartInfo psi = new ProcessStartInfo(foundOllama, "serve")
                    {
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };
                    psi.EnvironmentVariables["OLLAMA_FLASH_ATTENTION"] = "1";
                    psi.EnvironmentVariables["OLLAMA_NUM_PARALLEL"] = "1";
                    s_ollamaProcess = Process.Start(psi);
                    BindToJob(s_ollamaProcess);
                    if (s_ollamaProcess != null)
                    {
                        WritePidFile(projectRoot, "ollama.pid", s_ollamaProcess.Id);
                        WaitForEndpoint("http://127.0.0.1:11434/api/tags", 15, "Ollama LLM (11434)");
                        WriteSupervisorLog(projectRoot, "OK", string.Format("Ollama started (PID {0})", s_ollamaProcess.Id));
                    }
                }
            }
            catch { }
        }

        static bool StartBackend(string projectRoot)
        {
            try
            {
                string pyExe = Path.Combine(projectRoot, ".venv", "Scripts", "python.exe");
                if (!File.Exists(pyExe))
                {
                    PrintColor(string.Format("    [LỖI] Không tìm thấy Python tại: {0}", pyExe), ConsoleColor.Red);
                    return false;
                }

                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = pyExe,
                    Arguments = "-m uvicorn apps.api.main:app --host 127.0.0.1 --port 8000",
                    WorkingDirectory = projectRoot,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = false,
                    RedirectStandardError = false
                };

                psi.EnvironmentVariables["ALLOW_PRODUCTION_DB_WRITE"] = "false";
                psi.EnvironmentVariables["ENABLE_IN_PROCESS_SCHEDULER"] = "false";
                psi.EnvironmentVariables["INGESTION_SCHEDULER_ENABLED"] = "false";
                psi.EnvironmentVariables["PYTHONUNBUFFERED"] = "1";

                s_backendProcess = Process.Start(psi);
                BindToJob(s_backendProcess);
                WritePidFile(projectRoot, "backend.pid", s_backendProcess.Id);
                WriteSupervisorLog(projectRoot, "INFO", string.Format("Backend started (PID {0})", s_backendProcess.Id));
                PrintColor(string.Format("    -> Backend khởi chạy thành công (PID {0})", s_backendProcess.Id), ConsoleColor.DarkGreen);
                return true;
            }
            catch (Exception ex)
            {
                PrintColor(string.Format("    [LỖI] {0}", ex.Message), ConsoleColor.Red);
                return false;
            }
        }

        static bool StartFrontend(string projectRoot)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo
                {
                    FileName = "cmd.exe",
                    Arguments = "/c \"npm --prefix apps\\web run dev\"",
                    WorkingDirectory = projectRoot,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    RedirectStandardOutput = false,
                    RedirectStandardError = false
                };

                s_frontendProcess = Process.Start(psi);
                BindToJob(s_frontendProcess);
                WritePidFile(projectRoot, "frontend.pid", s_frontendProcess.Id);
                WriteSupervisorLog(projectRoot, "INFO", string.Format("Frontend started (PID {0})", s_frontendProcess.Id));
                PrintColor(string.Format("    -> Frontend khởi chạy thành công (PID {0})", s_frontendProcess.Id), ConsoleColor.DarkGreen);
                return true;
            }
            catch (Exception ex)
            {
                PrintColor(string.Format("    [LỖI] {0}", ex.Message), ConsoleColor.Red);
                return false;
            }
        }

        static bool WaitForEndpoint(string url, int timeoutSeconds, string label)
        {
            DateTime start = DateTime.Now;
            int dotCount = 0;

            while ((DateTime.Now - start).TotalSeconds < timeoutSeconds)
            {
                try
                {
                    HttpWebRequest req = (HttpWebRequest)WebRequest.Create(url);
                    req.Timeout = 1000;
                    req.Method = "GET";
                    using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                    {
                        if ((int)resp.StatusCode >= 200 && (int)resp.StatusCode < 400)
                        {
                            Console.Write("\r                                                                      \r");
                            PrintColor(string.Format("    -> {0} đã phản hồi HTTP {1} (Sẵn sàng)", label, (int)resp.StatusCode), ConsoleColor.Green);
                            return true;
                        }
                    }
                }
                catch
                {
                    dotCount++;
                    string dots = new string('.', (dotCount % 4) + 1);
                    Console.Write(string.Format("\r    Chờ {0}{1}   ", label, dots.PadRight(4)));
                }

                Thread.Sleep(500);
            }

            Console.WriteLine();
            return false;
        }

        static bool IsPortListening(int port)
        {
            try
            {
                using (var client = new System.Net.Sockets.TcpClient())
                {
                    var result = client.BeginConnect("127.0.0.1", port, null, null);
                    bool success = result.AsyncWaitHandle.WaitOne(400);
                    if (success && client.Connected)
                    {
                        client.EndConnect(result);
                        return true;
                    }
                }
            }
            catch { }
            return false;
        }

        static void ShutdownAll(string reason)
        {
            lock (s_lock)
            {
                if (s_isShuttingDown) return;
                s_isShuttingDown = true;

                Console.WriteLine();
                PrintColor("\n[*] Đang tắt an toàn toàn bộ dịch vụ InvestIntel...", ConsoleColor.Yellow);

                KillProcessTree(s_frontendProcess, "Frontend");
                KillProcessTree(s_backendProcess, "Backend");
                KillProcessTree(s_ollamaProcess, "Ollama");

                // Đảm bảo không còn tiến trình con treo trên cổng
                FreePortIfOccupied(8000);
                FreePortIfOccupied(3000);
                CleanPidFiles(null);

                if (s_jobHandle != IntPtr.Zero)
                {
                    CloseHandle(s_jobHandle);
                    s_jobHandle = IntPtr.Zero;
                }

                PrintColor("[OK] Đã tắt sạch sẽ tất cả dịch vụ. Tạm biệt!", ConsoleColor.Green);
            }
        }

        static void KillProcessTree(Process proc, string name)
        {
            if (proc == null) return;
            try
            {
                if (!proc.HasExited)
                {
                    int pid = proc.Id;
                    Process kp = Process.Start(new ProcessStartInfo("taskkill", string.Format("/F /T /PID {0}", pid))
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false
                    });
                    if (kp != null) kp.WaitForExit(1500);
                }
            }
            catch { }
        }

        static void PrintColor(string msg, ConsoleColor color)
        {
            ConsoleColor old = Console.ForegroundColor;
            Console.ForegroundColor = color;
            Console.WriteLine(msg);
            Console.ForegroundColor = old;
        }
    }
}
