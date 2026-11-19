"use client";

import * as React from "react";
import { useEffect, useState } from "react";
import { BlackHoleHeroSection } from "@/components/ui/blackhole-hero-section";
import {
  Scissors,
  Sparkles,
  Zap,
  Play,
  ArrowRight,
  ShieldCheck,
  Cpu,
  Download,
  Flame,
} from "lucide-react";

/** Responsive hook to detect mobile viewport and adjust camera perspective */
function useNarrow(query = "(max-width: 767px)") {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const m = window.matchMedia(query);
    const sync = () => setNarrow(m.matches);
    sync();
    m.addEventListener("change", sync);
    return () => m.removeEventListener("change", sync);
  }, [query]);
  return narrow;
}

export interface FinalBossGetStartedProps {
  onGetStarted?: () => void;
  onExploreFeatures?: () => void;
}

export default function FinalBossGetStarted({
  onGetStarted,
  onExploreFeatures,
}: FinalBossGetStartedProps) {
  const narrow = useNarrow();

  return (
    <div className="relative min-h-screen w-full bg-[#0a0a0c] text-white selection:bg-purple-500 selection:text-white">
      {/* Black Hole Hero Section */}
      <section className="relative min-h-[92svh] w-full md:min-h-[760px]">
        <BlackHoleHeroSection
          focus={narrow ? [0.5, 0.78] : [0.72, 0.48]}
          scrim={narrow ? "top" : "left"}
          scrimStrength={0.92}
          distance={24}
          elevation={narrow ? -7 : -5.5}
          fov={narrow ? 58 : 42}
          glow={narrow ? 0.9 : 1.1}
          steps={narrow ? 200 : 320}
          resolution={narrow ? 0.65 : 0.75}
        >
          <div className="flex h-full min-h-[92svh] items-start px-6 pt-16 sm:px-10 md:min-h-[760px] md:items-center md:pt-0 lg:px-20">
            <div className="max-w-[42rem]">
              {/* Badge */}
              <div className="inline-flex items-center gap-2 rounded-full border border-purple-500/30 bg-purple-950/40 px-3.5 py-1.5 text-xs font-medium text-purple-300 backdrop-blur-md mb-6">
                <Flame className="h-3.5 w-3.5 text-amber-400" />
                <span>Clipping Final Boss • 100% Local & Free</span>
              </div>

              {/* Headline */}
              <h1 className="text-[2.6rem] font-extrabold leading-[1.08] tracking-[-0.03em] text-white sm:text-6xl lg:text-[4.25rem]">
                Final Boss
                <br />
                <span className="bg-gradient-to-r from-purple-400 via-pink-400 to-amber-300 bg-clip-text text-transparent">
                  Get Started
                </span>
              </h1>

              {/* Subheading / Copy */}
              <p className="mt-6 max-w-xl text-[1.05rem] leading-relaxed text-white/70 md:mt-7">
                Leave free clipping on that first page. Turn long YouTube videos,
                Twitch streams, and raw footage into ranked 9:16 short clips with
                animated captions and AI virality scoring—powered completely on
                your local hardware. Zero API keys, zero watermarks, zero limits.
              </p>

              {/* Action Buttons */}
              <div className="mt-8 flex flex-wrap items-center gap-4 md:mt-10">
                <button
                  type="button"
                  onClick={onGetStarted}
                  className="group inline-flex items-center gap-2 rounded-full bg-white px-7 py-3.5 text-sm font-semibold text-black transition-all duration-200 hover:bg-white/90 hover:scale-[1.02] active:scale-[0.98] shadow-lg shadow-white/10"
                >
                  <Scissors className="h-4 w-4 text-purple-600 transition-transform group-hover:rotate-12" />
                  <span>Start Free Clipping</span>
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </button>

                <button
                  type="button"
                  onClick={onExploreFeatures}
                  className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/5 px-6 py-3.5 text-sm font-medium text-white/90 backdrop-blur-md transition-all duration-200 hover:border-white/40 hover:bg-white/10 hover:text-white"
                >
                  <Play className="h-4 w-4 text-amber-400" />
                  <span>How Free Clipping Works</span>
                </button>
              </div>

              {/* Quick Feature Pillars */}
              <div className="mt-12 grid grid-cols-3 gap-4 border-t border-white/10 pt-6">
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-white/90">
                    <ShieldCheck className="h-4 w-4 text-emerald-400" />
                    <span>Free Forever</span>
                  </div>
                  <p className="mt-1 text-[0.8rem] text-white/50">
                    No subscriptions or quotas
                  </p>
                </div>
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-white/90">
                    <Cpu className="h-4 w-4 text-purple-400" />
                    <span>100% Local</span>
                  </div>
                  <p className="mt-1 text-[0.8rem] text-white/50">
                    Whisper + peak scoring
                  </p>
                </div>
                <div>
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-white/90">
                    <Zap className="h-4 w-4 text-amber-400" />
                    <span>Auto 9:16 Shorts</span>
                  </div>
                  <p className="mt-1 text-[0.8rem] text-white/50">
                    Kinetic TikTok captions
                  </p>
                </div>
              </div>
            </div>
          </div>
        </BlackHoleHeroSection>
      </section>

      {/* Free Clipping Features & Unsplash Visual Showcase */}
      <section className="relative z-20 border-t border-white/10 bg-[#0d0e12] px-6 py-20 sm:px-10 lg:px-20">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <span className="text-xs font-semibold uppercase tracking-wider text-purple-400">
              Leave Free Clipping On That First Page
            </span>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">
              Everything You Need to Dominate Short-Form Video
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-sm text-white/60">
              Download, transcribe, rank, edit, and export viral clips in seconds.
              No cloud accounts or recurring fees required.
            </p>
          </div>

          <div className="mt-14 grid grid-cols-1 gap-8 md:grid-cols-3">
            {/* Feature 1 */}
            <div className="group overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02] p-4 transition-all hover:border-purple-500/40 hover:bg-white/[0.04]">
              <div className="relative h-48 w-full overflow-hidden rounded-xl">
                <img
                  src="https://images.unsplash.com/photo-1574717024653-61fd2cf4d44d?auto=format&fit=crop&w=800&q=80"
                  alt="Video editing studio timeline"
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                <span className="absolute bottom-3 left-3 rounded-md bg-purple-600/90 px-2 py-1 text-[11px] font-medium text-white">
                  9:16 Auto Layout
                </span>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-white">
                Smart Frame Re-centering
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-white/60">
                Automatically crop 16:9 widescreen or blur-fit backgrounds to
                produce flawless vertical videos tailored for TikTok, Reels, and
                Shorts.
              </p>
            </div>

            {/* Feature 2 */}
            <div className="group overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02] p-4 transition-all hover:border-pink-500/40 hover:bg-white/[0.04]">
              <div className="relative h-48 w-full overflow-hidden rounded-xl">
                <img
                  src="https://images.unsplash.com/photo-1534423861386-85a16f5d13fd?auto=format&fit=crop&w=800&q=80"
                  alt="Streaming broadcast setup"
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                <span className="absolute bottom-3 left-3 rounded-md bg-pink-600/90 px-2 py-1 text-[11px] font-medium text-white">
                  Stream Watcher
                </span>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-white">
                Pinned Streamer Watcher
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-white/60">
                Pin your favorite Twitch, YouTube, or Kick creators. Automatically
                fetch VODs and generate highlight reels as soon as they go offline.
              </p>
            </div>

            {/* Feature 3 */}
            <div className="group overflow-hidden rounded-2xl border border-white/10 bg-white/[0.02] p-4 transition-all hover:border-amber-500/40 hover:bg-white/[0.04]">
              <div className="relative h-48 w-full overflow-hidden rounded-xl">
                <img
                  src="https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?auto=format&fit=crop&w=800&q=80"
                  alt="Dynamic captions and audio visualization"
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent" />
                <span className="absolute bottom-3 left-3 rounded-md bg-amber-600/90 px-2 py-1 text-[11px] font-medium text-white">
                  10 Caption Templates
                </span>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-white">
                Kinetic Word Animations
              </h3>
              <p className="mt-2 text-xs leading-relaxed text-white/60">
                Hormozi, MrBeast, Neon Pulse, Karaoke, and 6 more high-retention
                caption animations rendered with pixel-perfect ffmpeg fidelity.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
