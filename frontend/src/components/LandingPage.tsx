import { useState } from "react";
import type { KeyboardEvent } from "react";

interface LandingPageProps {
    onLaunch: (prompt: string, sessionId: string) => void;
}

export default function LandingPage({ onLaunch }: LandingPageProps) {
    const [prompt, setPrompt] = useState("");
    const [isLaunching, setIsLaunching] = useState(false);
    const [deployStep, setDeployStep] = useState(0);

    const deploySequence = [
        "Initializing Agent Network...",
        "Deploying Cognitive Nodes...",
        "Establishing Consensus Protocols...",
        "Live."
    ];

    const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setPrompt(e.target.value);
        e.target.style.height = "auto";
        e.target.style.height = `${e.target.scrollHeight}px`;
    };

    // Recalculate if setPrompt is triggered externally (e.g. chips)
    const handleChipClick = (text: string) => {
        setPrompt(text);
        const textarea = document.getElementById("prompt-textarea");
        if (textarea) {
            textarea.style.height = "auto";
            setTimeout(() => {
                textarea.style.height = `${textarea.scrollHeight}px`;
            }, 0);
        }
    };

    const handleLaunch = async () => {
        if (!prompt.trim() || isLaunching) return;
        setIsLaunching(true);
        setDeployStep(0);

        try {
            // 1. Fire off the backend request immediately
            const res = await fetch("http://127.0.0.1:8000/api/launch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt }),
            });

            if (!res.ok) {
                console.error("Failed to launch swarm");
                setIsLaunching(false);
                return;
            }

            const data = await res.json();
            const newSessionId = data.session_id;

            // 2. Run the cinematic deploy sequence
            for (let i = 1; i < deploySequence.length; i++) {
                await new Promise(r => setTimeout(r, 800)); // 800ms per step
                setDeployStep(i);
            }

            await new Promise(r => setTimeout(r, 400)); // brief pause on "Live."

            // 3. Complete launch
            onLaunch(prompt, newSessionId);

        } catch (e) {
            console.error(e);
            setIsLaunching(false);
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleLaunch();
        }
    };

    return (
        <div className="flex flex-col items-center justify-center flex-1 bg-[#0A0A0A] text-white p-6 w-full animate-fade-in relative overflow-hidden">
            {/* Dynamic Background during launch */}
            {isLaunching && (
                <div className="absolute inset-0 bg-gradient-to-b from-purple-900/10 to-transparent animate-pulse pointer-events-none" />
            )}

            <div className="w-full max-w-2xl text-center space-y-8 relative z-10 transition-transform duration-700 ease-in-out" style={{
                transform: isLaunching ? "translateY(-5vh)" : "translateY(0)"
            }}>

                {/* Header Section */}
                <div className="space-y-4">
                    <div className="inline-block px-3 py-1 rounded-full border border-gray-800 bg-gray-900/50 text-xs font-mono text-gray-400 tracking-wider uppercase mb-2">
                        Multi-Agent Swarm Sandbox
                    </div>
                    <h1 className="text-5xl font-serif tracking-tight text-white mb-4">
                        Agent Network
                    </h1>
                    <p className="text-gray-400 text-lg max-w-xl mx-auto leading-relaxed">
                        Deploy an autonomous, non-hierarchical swarm of agents to debate complex problems, synthesize research, and organically reach consensus.
                    </p>
                </div>

                {/* Search Bar Section */}
                <div className="relative group mt-12">
                    <div className="absolute inset-0 bg-white/5 rounded-2xl blur-xl group-hover:bg-white/10 transition-colors duration-500" />
                    <div className="relative flex items-center bg-[#141414] border border-gray-800 rounded-2xl overflow-hidden focus-within:border-white/30 focus-within:ring-1 focus-within:ring-white/30 transition-all duration-300">
                        <div className="pl-6 text-gray-500">
                            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                        </div>
                        <textarea
                            id="prompt-textarea"
                            value={prompt}
                            onChange={handleInput}
                            onKeyDown={handleKeyDown}
                            disabled={isLaunching}
                            className="w-full bg-transparent text-white placeholder-gray-600 px-4 py-6 outline-none text-lg disabled:opacity-50 resize-none overflow-hidden"
                            style={{ minHeight: '76px' }}
                            placeholder="What should the swarm research?"
                            autoFocus
                            rows={1}
                        />
                        <button
                            onClick={handleLaunch}
                            disabled={!prompt.trim() || isLaunching}
                            className="pr-6 pl-4 py-6 text-gray-400 hover:text-white disabled:hover:text-gray-400 transition-colors"
                        >
                            {isLaunching ? (
                                <div className="w-5 h-5 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                            ) : (
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 5l7 7m0 0l-7 7m7-7H3" />
                                </svg>
                            )}
                        </button>
                    </div>

                    {/* Deploy Animation Terminal */}
                    {isLaunching && (
                        <div className="absolute top-full left-0 right-0 mt-6 bg-[#141414] border border-gray-800 rounded-xl p-4 text-left font-mono text-sm shadow-2xl animate-fade-in">
                            <div className="flex items-center gap-2 text-gray-500 mb-2 pb-2 border-b border-gray-800/50 text-[10px] tracking-widest uppercase">
                                <span className="w-2 h-2 rounded-full bg-red-500/50" />
                                <span className="w-2 h-2 rounded-full bg-yellow-500/50" />
                                <span className="w-2 h-2 rounded-full bg-green-500/50" />
                                <span className="ml-2">System Deployment</span>
                            </div>
                            <div className="space-y-1.5 pl-1">
                                {deploySequence.map((step, idx) => (
                                    <div
                                        key={idx}
                                        className={`flex items-center gap-2 transition-all duration-300 ${idx < deployStep ? "text-gray-400" :
                                            idx === deployStep ? "text-green-400 font-semibold" :
                                                "opacity-0 h-0 overflow-hidden"
                                            }`}
                                    >
                                        <span className="text-gray-600">&gt;</span>
                                        {step}
                                        {idx === deployStep && step !== "Live." && (
                                            <span className="w-1.5 h-3 bg-green-400 animate-pulse inline-block ml-1" />
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>

                {/* Example Chips - Fade out during launch */}
                <div className={`flex flex-wrap items-center justify-center gap-2 mt-8 text-sm pt-4 transition-opacity duration-500 ${isLaunching ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
                    <span className="text-gray-600 mr-2">Try:</span>
                    {[
                        { label: "Market Research", pt: "Search the web to conduct market research on the emerging humanoid robotics industry (e.g., Figure, 1X, Tesla Optimus). Identify the total addressable market, key drivers, and debate the go-to-market strategies. Synthesize a comprehensive market report." },
                        { label: "Competitor Analysis", pt: "We are an AI startup building open-source LLMs. Search the web for a competitor analysis of Mistral, Meta Llama, and Qwen. Debate their pricing strategies, developer adoption, and pinpoint their biggest vulnerabilities. Synthesize a strategy for how we can differentiate." },
                        { label: "Product Comparison", pt: "Search the web to compare the technical limitations of the Humane AI Pin versus the Rabbit R1. Debate their hardware flaws, user experience design, and synthesize a consensus on which product failure is more critical." }
                    ].map((example) => (
                        <button
                            key={example.label}
                            onClick={() => handleChipClick(example.pt)}
                            className="px-4 py-2 rounded-full bg-gray-900 border border-gray-800 text-gray-400 hover:text-white hover:bg-gray-800 transition-colors cursor-pointer"
                        >
                            {example.label}
                        </button>
                    ))}
                </div>

            </div>
        </div>
    );
}
