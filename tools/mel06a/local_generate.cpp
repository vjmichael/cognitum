// MEL-06A bounded offline CPU reference driver. No network or tool authority.
#include "llama.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>
#include <stdexcept>
#include <memory>
static std::string read_file(const char* p) {
    std::ifstream f(p,std::ios::binary); if(!f)throw std::runtime_error("file read");
    std::string s((std::istreambuf_iterator<char>(f)),{}); if(s.size()>65536)throw std::runtime_error("input limit");return s;
}
int main(int argc,char** argv){
 try {
    if(argc!=6)throw std::runtime_error("usage: driver model prompt grammar max_tokens threads");
    int max_tokens=std::stoi(argv[4]),threads=std::stoi(argv[5]);
    if(max_tokens<1||max_tokens>512||threads<1||threads>8)throw std::runtime_error("limits");
    auto prompt=read_file(argv[2]);auto grammar=read_file(argv[3]);
    ggml_backend_load_all(); auto mp=llama_model_default_params();mp.n_gpu_layers=0;
    std::unique_ptr<llama_model,decltype(&llama_model_free)> m(llama_model_load_from_file(argv[1],mp),llama_model_free);
    if(!m)throw std::runtime_error("model load");auto* vocab=llama_model_get_vocab(m.get());
    int count=-llama_tokenize(vocab,prompt.data(),prompt.size(),nullptr,0,true,true);
    if(count<1||count+max_tokens>4096)throw std::runtime_error("context limit");
    std::vector<llama_token> toks(count);if(llama_tokenize(vocab,prompt.data(),prompt.size(),toks.data(),toks.size(),true,true)!=count)throw std::runtime_error("tokenize");
    auto cp=llama_context_default_params();cp.n_ctx=4096;cp.n_batch=4096;cp.n_threads=threads;cp.n_threads_batch=threads;cp.no_perf=false;
    std::unique_ptr<llama_context,decltype(&llama_free)> ctx(llama_init_from_model(m.get(),cp),llama_free);if(!ctx)throw std::runtime_error("context");
    auto sp=llama_sampler_chain_default_params();std::unique_ptr<llama_sampler,decltype(&llama_sampler_free)> sample(llama_sampler_chain_init(sp),llama_sampler_free);
    if(!grammar.empty()){auto* g=llama_sampler_init_grammar(vocab,grammar.c_str(),"root");if(!g)throw std::runtime_error("grammar");llama_sampler_chain_add(sample.get(),g);}
    llama_sampler_chain_add(sample.get(),llama_sampler_init_greedy());
    auto batch=llama_batch_get_one(toks.data(),toks.size());int generated=0;bool eog=false;
    for(;generated<max_tokens;++generated){if(llama_decode(ctx.get(),batch))throw std::runtime_error("decode");auto token=llama_sampler_sample(sample.get(),ctx.get(),-1);if(llama_vocab_is_eog(vocab,token)){eog=true;break;}
        char piece[4096];int n=llama_token_to_piece(vocab,token,piece,sizeof(piece),0,false);if(n<0)throw std::runtime_error("piece limit");std::cout.write(piece,n);std::cout.flush();batch=llama_batch_get_one(&token,1);
        // batch references token; decode before it goes out of scope (store in vector).
        toks[0]=token;batch=llama_batch_get_one(toks.data(),1);
    }
    std::cerr<<"MEL06 tokens_prompt="<<count<<" tokens_generated="<<generated<<" eog="<<eog<<"\n";
    return 0;
 } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
