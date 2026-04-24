"use client";

import type { CSSProperties } from "react";
import { useCallback, useEffect, useMemo, useState } from "react";

import styles from "./site-intro.module.css";

const INTRO_DISABLED_KEY = "askora-site-intro-disabled-v2";
const CLOSE_ANIMATION_MS = 420;
const INTRO_SCROLL_TARGET = 900;

type DismissMode = "session" | "permanent";

type ParticleSpec = {
  left: string;
  top: string;
  x: string;
  y: string;
  duration: string;
  delay: string;
};

const STATUS_ITEMS = [
  {
    title: "Семантический слой",
    description: "Бизнес-метрики и словарь терминов загружены.",
  },
  {
    title: "SQL guardrails",
    description: "Проверка безопасности активна до выполнения запроса.",
  },
  {
    title: "Askora",
    description: "Запросы, отчёты, группы и визуализация готовы к работе.",
  },
];

function buildParticles(reducedMotion: boolean): ParticleSpec[] {
  const count = reducedMotion ? 14 : 28;

  return Array.from({ length: count }, (_, index) => {
    const side = index % 4;
    const base = (index * 17 + 11) % 100;
    let left = 50;
    let top = 50;

    if (side === 0) {
      left = 14 + (base % 72);
      top = 10 + (base % 10);
    }
    if (side === 1) {
      left = 82 + (base % 9);
      top = 14 + (base % 66);
    }
    if (side === 2) {
      left = 14 + (base % 72);
      top = 82 + (base % 9);
    }
    if (side === 3) {
      left = 10 + (base % 10);
      top = 14 + (base % 66);
    }

    const x = ((index % 2 === 0 ? 1 : -1) * (60 + (index * 11) % 95)).toString();
    const y = (((index + 1) % 2 === 0 ? 1 : -1) * (48 + (index * 13) % 88)).toString();

    return {
      left: `${left}%`,
      top: `${top}%`,
      x: `${x}px`,
      y: `${y}px`,
      duration: `${3.8 + (index % 6) * 0.55}s`,
      delay: `${(index % 7) * 0.42}s`,
    };
  });
}

export function SiteIntro() {
  const [mounted, setMounted] = useState(false);
  const [isVisible, setIsVisible] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [reducedMotion, setReducedMotion] = useState(false);

  const particles = useMemo(() => buildParticles(reducedMotion), [reducedMotion]);
  const progress = Math.min(scrollProgress / INTRO_SCROLL_TARGET, 1);

  useEffect(() => {
    setMounted(true);

    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const applyReducedMotion = () => setReducedMotion(media.matches);
    applyReducedMotion();

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", applyReducedMotion);
    } else {
      media.addListener(applyReducedMotion);
    }

    const params = new URLSearchParams(window.location.search);
    const forcedOpen = params.get("intro") === "1";

    if (forcedOpen) {
      window.localStorage.removeItem(INTRO_DISABLED_KEY);
    }

    const isDisabled = window.localStorage.getItem(INTRO_DISABLED_KEY) === "1";
    if (!isDisabled) {
      setIsVisible(true);
    }

    return () => {
      if (typeof media.removeEventListener === "function") {
        media.removeEventListener("change", applyReducedMotion);
      } else {
        media.removeListener(applyReducedMotion);
      }
    };
  }, []);

  const dismiss = useCallback((mode: DismissMode) => {
    if (!mounted || isClosing) {
      return;
    }

    if (mode === "permanent") {
      window.localStorage.setItem(INTRO_DISABLED_KEY, "1");
    }

    setIsClosing(true);
    window.setTimeout(() => {
      setIsVisible(false);
      setIsClosing(false);
    }, CLOSE_ANIMATION_MS);
  }, [isClosing, mounted]);

  const advanceIntro = useCallback((delta: number) => {
    if (isClosing || !isVisible) {
      return;
    }
    setScrollProgress((current) => {
      const next = Math.max(0, Math.min(current + delta, INTRO_SCROLL_TARGET));
      if (next >= INTRO_SCROLL_TARGET) {
        window.setTimeout(() => dismiss("session"), 120);
      }
      return next;
    });
  }, [dismiss, isClosing, isVisible]);

  useEffect(() => {
    if (!isVisible || isClosing) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        dismiss("session");
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [dismiss, isVisible, isClosing]);

  if (!mounted || !isVisible) {
    return null;
  }

  return (
    <div
      className={`${styles.overlay} ${isClosing ? styles.closing : ""}`}
      role="dialog"
      aria-modal="true"
      aria-label="Интро Askora"
      onWheel={(event) => {
        if (event.deltaY > 0) {
          advanceIntro(event.deltaY);
        }
      }}
      onTouchMove={(event) => {
        if (event.touches.length !== 1) {
          return;
        }
        const y = event.touches[0]?.clientY ?? 0;
        const last = Number((event.currentTarget as HTMLDivElement).dataset.lastY ?? y);
        const delta = Math.max(0, last - y);
        (event.currentTarget as HTMLDivElement).dataset.lastY = String(y);
        if (delta > 0) {
          advanceIntro(delta * 2.2);
        }
      }}
      onTouchStart={(event) => {
        const y = event.touches[0]?.clientY ?? 0;
        (event.currentTarget as HTMLDivElement).dataset.lastY = String(y);
      }}
    >
      <div className={styles.backdrop} />
      <div className={styles.frame}>
        <div className={styles.cornerTopLeft} />
        <div className={styles.cornerTopRight} />
        <div className={styles.cornerBottomLeft} />
        <div className={styles.cornerBottomRight} />

        <div className={styles.content}>
          <section className={styles.copyBlock}>
            <div className={styles.kicker}>Askora — AI-ассистент запросов</div>
            <h1 className={styles.title}>Askora</h1>
            <p className={styles.description}>
              Askora понимает запросы на русском, объясняет, как она поняла вопрос, строит безопасный SQL и помогает быстро
              перейти от идеи к готовому отчёту.
            </p>

            <div className={styles.statusGrid}>
              {STATUS_ITEMS.map((item) => (
                <div className={styles.statusCard} key={item.title}>
                  <div className={styles.statusTitle}>{item.title}</div>
                  <div className={styles.statusDescription}>{item.description}</div>
                </div>
              ))}
            </div>

            <div className={styles.progressPanel}>
              <div className={styles.progressHeader}>
                <span>Прокрутите интро</span>
                <span>{Math.round(progress * 100)}%</span>
              </div>
              <div className={styles.progressTrack}>
                <span className={styles.progressFill} style={{ width: `${progress * 100}%` }} />
              </div>
              <p className={styles.progressHint}>
                Пролистайте интро колесом или свайпом вниз. После полного прогресса Askora откроется автоматически.
              </p>
            </div>

            <div className={styles.actions}>
              <button className={styles.primaryButton} onClick={() => dismiss("session")} type="button">
                Открыть Askora
              </button>
              <button className={styles.secondaryButton} onClick={() => dismiss("permanent")} type="button">
                Больше не показывать
              </button>
            </div>
          </section>

          <section className={styles.visualBlock} aria-hidden="true">
            <div className={styles.logoWrap}>
              <div className={styles.logoMotion}>
                <div className={styles.rings}>
                  <div className={`${styles.ring} ${styles.ringOne}`} />
                  <div className={`${styles.ring} ${styles.ringTwo}`} />
                  <div className={`${styles.ring} ${styles.ringThree}`} />
                  <div className={`${styles.ring} ${styles.ringFour}`} />
                </div>
                <div className={styles.flare} />
                <div className={styles.particles}>
                  {particles.map((particle, index) => (
                    <span
                      key={`${particle.left}-${particle.top}-${index}`}
                      className={styles.particle}
                      style={
                        {
                          left: particle.left,
                          top: particle.top,
                          "--particle-x": particle.x,
                          "--particle-y": particle.y,
                          "--particle-duration": particle.duration,
                          "--particle-delay": particle.delay,
                        } as CSSProperties
                      }
                    />
                  ))}
                </div>
                <div className={styles.logoGlow} />
                <div className={styles.logoOutline} />
                <video
                  className={styles.logo}
                  autoPlay
                  loop
                  muted
                  playsInline
                  preload="auto"
                  aria-label="Неоновый логотип"
                >
                  <source src="/intro-cat-logo.webm" type="video/webm" />
                </video>
              </div>
            </div>

            <div className={styles.hud}>
              <span className={styles.hudDot} />
              <span>askora готова</span>
            </div>
          </section>
        </div>

        <div className={styles.noise} />
        <div className={styles.scanlines} />
        <div className={styles.vignette} />
      </div>
    </div>
  );
}
