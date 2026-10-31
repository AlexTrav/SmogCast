<template>
  <!-- знак SmogCast: заснеженная вершина, над ней солнце, сквозь воздух – частицы взвеси -->
  <svg viewBox="0 0 40 40" aria-hidden="true">
    <defs>
      <linearGradient id="logo-sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#1f6fd1" />
        <stop offset="1" stop-color="#f0a46a" />
      </linearGradient>
    </defs>
    <rect width="40" height="40" rx="11" fill="url(#logo-sky)" />
    <circle cx="27" cy="13" r="4.2" fill="#ffe2b8" />
    <path d="M4 32 L15 17 L20 23 L25 18 L36 32 Z" fill="#0c1a2e" opacity="0.85" />
    <path d="M15 17 L18.2 21.3 L16.4 22 L14.6 20.6 L12.6 20.4 Z" fill="#ffffff" />
    <circle cx="9" cy="12" r="1" fill="#fff" opacity="0.7" />
    <circle cx="13" cy="8" r="0.8" fill="#fff" opacity="0.55" />
    <circle cx="33" cy="22" r="0.9" fill="#fff" opacity="0.6" />
  </svg>
</template>
