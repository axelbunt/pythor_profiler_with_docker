## Python Profiler

Vacancy test task:  

> Implement a Python tracing utility that measures the execution time of specific functions in a python program. You should be able to:
> - [x] Enable profiling at an arbitrary moment providing set of functions to trace.
> - [x] Disable profiling and get the results.
>
> Bonus Features:  
> - [x] Allow toggling function list dynamically (e.g. without disabling it).  
> - [x] Allow to get intermediate results while profiling is running.
> 
> Requirements:  
> - [x] Implement the tracing without modifying the target functions directly.  
> - [x] Provide a simple way to specify which > functions to track (e.g., via a configuration file or a decorator).  
> - [x] Ensure minimal overhead when tracing is disabled.  
> - [x] Format and display results in a clear manner (e.g., as a table in the console).


### Sampling Profiler Approach
To achive minimal overhead when tracing is disabled, we should make something like [Statistical/Sampler profiler](https://en.wikipedia.org/wiki/Profiling_(computer_programming)#Statistical_profilers).

> Sampling profiles are typically less numerically accurate and specific, but allow the target program to run at near full speed.

With this type profilers we'll always get some *innacurity*:

> The actual amount of error is usually more than one sampling period. In fact, if a value is n times the sampling period, the expected error in it is the square-root of n sampling periods. If the sampling period is 0.01 seconds and foo's run-time is 1 second, the expected error in foo's run-time is 0.1 seconds. It is likely to vary this much on the average from one profiling run to the next. (Sometimes it will vary more.)[¹](https://web.archive.org/web/20120529075000/http://www.cs.utah.edu/dept/old/texinfo/as/gprof.html#:~:text=The%20actual%20amount,will%20vary%20more.)

---

If we want to trace program running in another process, we need to use [`ptrace`](https://en.wikipedia.org/wiki/Ptrace) system function. Problem is, that every OS has its own implementation... So I desiced to make task a little bit simpler and used Docker to get rid of platform-dependent stuff (getting crossplatform-working user experience is very time consuming). To implement getting process call stack I used [LLDB](https://lldb.llvm.org/) with [cpython-lldb](https://github.com/malor/cpython-lldb) extension.  

Unfortunately, my solution gives us a lot overhead when profiler is active (operating profiling process via LLDB + of course Python is not really fast). So in this way we can't get high accuracy: I've got something around *150 ms per sample*, while `sampling_timeout` is 20 ms.  

It’s not ideal, but it works — already provides useful insights that could help in real-world applications. 🙃
You can now retrieve the total runtime of specific functions and identify which ones are the most time-consuming. These are likely to be bottlenecks in your program.  
A future improvement would be to implement call graph generation — this would show the full function call paths, providing additional tips for optimization.

Let's get to profiler architecture overview.

### Profiler Process Structure
```
Profiler Process
├── Main thread -- Operates Profiler CLI.
└── Sampling thread -- Gets sample of selected Python Process every \delta_t seconds. Has its own LLDB instance, which do all sampling stuff.
```

### Getting Started with Sample Profiler
Build and run docker contaner:
```bash
docker build -t sample_profiler .

docker run -it --cap-add=SYS_PTRACE --security-opt seccomp=unconfined sample_profiler
```
> More info about parameters `--cap-add=SYS_PTRACE --security-opt seccomp=unconfined`:  
https://github.com/rr-debugger/rr/wiki/Docker  
https://docs.docker.com/engine/security/seccomp/

In Docker container:
```bash
python3 main.py &  # Run main program in bachground. Here is example program.
# Returns:
# [1] <pid>

# Copy this pid and run
python3 profiler.py start -p <pid> -f disk_io heavy_computation network_request
# Returns:
# Sampling functions: {'heavy_computation', 'network_request', 'disk_io'}
# Starting profiling process <pid> for functions: {'heavy_computation', 'network_request', 'disk_io'}
# Entering Profiler CLI. Type commands or 'exit' to quit.
# > 
```

After the profiler has started, you can interact with it live via the CLI by entering the following commands:
```bash
usage: profiler.py [-h] {start,stop,add,remove,results,status,exit} ...

Profiler CLI

positional arguments:
  {start,stop,add,remove,results,status,exit}
    start               Run profiler with certain arguments.
    stop                Stop profiler.
    add                 Add functions to profiling.
    remove              Remove functions from profiling.
    results             Get intermediate profiling results.
    status              Get profiler status.
    exit                Exit Profiler CLI.

optional arguments:
  -h, --help            show this help message and exit
```

```bash
# start
usage: profiler.py start [-h] -p PID -f FUNC [FUNC ...] [-t TIMEOUT]

optional arguments:
  -h, --help            show this help message and exit
  -p PID, --pid PID     PID of process you want to profile.
  -f FUNC [FUNC ...], --func FUNC [FUNC ...]
                        List of functions you want to profile in selected Python process.
  -t TIMEOUT, --timeout TIMEOUT
                        Custom sampling timout. Default is 0.02 s
```

```bash
# add
usage: profiler.py add [-h] -f FUNC [FUNC ...]

optional arguments:
  -h, --help            show this help message and exit
  -f FUNC [FUNC ...], --func FUNC [FUNC ...]
                        List of functions you want to profile in selected Python process.
```

```bash
# remove
usage: profiler.py remove [-h] -f FUNC [FUNC ...]

optional arguments:
  -h, --help            show this help message and exit
  -f FUNC [FUNC ...], --func FUNC [FUNC ...]
                        List of functions you want to remove from profiling in selected Python process.
```

---

After target process is ended, you will get pretty-formatted result:
```bash
> Profiler stopped.
╭───────────────────┬──────────────────────────────╮
│ Function Name     │ Approximate execution time   │
├───────────────────┼──────────────────────────────┤
│ heavy_computation │ 2.18 ± 0.2088                │
│ disk_io           │ 2.01 ± 0.1789                │
│ network_request   │ 1.82 ± 0.18                  │
╰───────────────────┴──────────────────────────────╯
```

### ToDo
- Add command to CLI that allows to change sampling_timeout dynamically.
- Redesign `results` command, so that it'll show all target functions. Now it shows only functions, that were sampled at least once. Results should look like this (if `heavy_computation` was not sampled):
```bash
> Profiler stopped.
╭───────────────────┬──────────────────────────────╮
│ Function Name     │ Approximate execution time   │
├───────────────────┼──────────────────────────────┤
│ heavy_computation │ No Data Available            │
│ disk_io           │ 2.01 ± 0.1789                │
│ network_request   │ 1.82 ± 0.18                  │
╰───────────────────┴──────────────────────────────╯
```
