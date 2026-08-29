#include <bits/stdc++.h>
#include <chrono>
#include <thread>
#include <mutex>
#include <db/db.hpp>
using namespace std;
using namespace chrono;
using namespace mvdb;
DB* db;

bool db_put( string key,  string value)
{
    db->put(key,value);
    return true;
}

string db_get(string key)
{
        return db->get(key);
}


bool db_delete_key( string key)
{
    db->del(key);
    return true;
}


struct Result
{
    double avg_latency_ms;
    long long ops;
    double throughput_ops_sec;
};

// Measure a generic operation
template <typename Func>
Result measure(const string &label, long long N, Func f)
{
    auto start = high_resolution_clock::now();

    for (long long i = 0; i < N; i++)
        f(i);

    auto end = high_resolution_clock::now();
    double total_ms = duration_cast<microseconds>(end - start).count() / 1000.0;

    cout << "\n--- " << label << " ---\n";
    cout << "Total ops: " << N << "\n";
    cout << "Time: " << total_ms << " ms\n";
    cout << "Avg latency: " << (total_ms / N) << " ms/op\n";
    cout << "Throughput: " << (N / (total_ms / 1000.0)) << " ops/sec\n";

    Result r;
    r.avg_latency_ms = total_ms / N;
    r.ops = N;
    r.throughput_ops_sec = (N / (total_ms / 1000.0));
    return r;
}

// Multi-thread test
void thread_worker(long long ops, atomic<long long> &counter, mutex &io_mtx)
{
    for (long long i = 0; i < ops; i++)
    {
        string key = "key_" + to_string(i);
        db_put(key, "value_" + to_string(i));
        db_get(key);
        counter++;
    }
}

int main()
{
    db = new DB("testdb_perf", 1024 * 1024 * 10);
    long long N = 100000; 

    cout << "============== MiniVault DB PERFORMANCE TEST ==============\n";
    cout << "Operations: " << N << "\n\n";

   
    measure("Sequential PUT", N, [&](long long i)
            { db_put("key_" + to_string(i), "value_" + to_string(i)); });

    
    // // 2. SEQUENTIAL GET TEST
   
    measure("Sequential GET", N, [&](long long i)
            { db_get("key_" + to_string(i)); });

   
    // 3. RANDOM GET TEST

    std::mt19937_64 rng(42);
    std::uniform_int_distribution<long long> dist(0, N - 1);

    measure("Random GET", N, [&](long long i)
            {
        long long id = dist(rng);
        db_get("key_" + to_string(id)); 
    });

 
    // 4. DELETE TEST
    
    measure("Delete", N, [&](long long i)
            { db_delete_key("key_" + to_string(i)); });


    // 5. MULTI-THREAD TEST
     cout << "\n--- Multi-thread stress test ---\n";
    int threads = 8;
    long long ops_per_thread = N / threads;

    atomic<long long> counter(0);
    mutex io_mtx;
    vector<thread> workers;

    auto t_start = high_resolution_clock::now();
    for (int i = 0; i < threads; i++)
    {
        workers.emplace_back(thread_worker, ops_per_thread, ref(counter), ref(io_mtx));
    }
    for (auto &t : workers)
        t.join();
    auto t_end = high_resolution_clock::now();

    double total_ms = duration_cast<microseconds>(t_end - t_start).count() / 1000.0;
    long long total_ops = counter.load();
    double throughput_mt = total_ops / (total_ms / 1000.0);

    cout << "Threads: " << threads << "\n";
    cout << "Total ops: " << total_ops << "\n";
    cout << "Total time: " << total_ms << " ms\n";
    cout << "Throughput: " << throughput_mt << " ops/sec\n";

    cout << "\n================= TEST COMPLETE =================\n";
}
