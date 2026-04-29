/* global React */
// Shared icons & primitives for RABELIA portal.
// All icons are 1.5px stroke, currentColor, 16px default.

const Icon = ({ name, size = 16, style }) => {
  const s = { width: size, height: size, flex: "none", display: "block", ...(style || {}) };
  const common = {
    width: size, height: size, viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round",
    style: s,
  };
  const paths = {
    doc: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h4"/></>,
    chat: <><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.4A8 8 0 1 1 21 12z"/></>,
    upload: <><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></>,
    send: <><path d="M22 2 11 13"/><path d="m22 2-7 20-4-9-9-4z"/></>,
    search: <><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></>,
    plus: <><path d="M12 5v14"/><path d="M5 12h14"/></>,
    check: <><path d="M20 6 9 17l-5-5"/></>,
    x: <><path d="M18 6 6 18"/><path d="m6 6 12 12"/></>,
    chevron_right: <><path d="m9 18 6-6-6-6"/></>,
    chevron_down: <><path d="m6 9 6 6 6-6"/></>,
    arrow_right: <><path d="M5 12h14"/><path d="m12 5 7 7-7 7"/></>,
    arrow_left: <><path d="M19 12H5"/><path d="m12 19-7-7 7-7"/></>,
    user: <><circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/></>,
    users: <><circle cx="9" cy="8" r="4"/><path d="M2 21a7 7 0 0 1 14 0"/><path d="M16 4a4 4 0 0 1 0 8"/><path d="M22 21a7 7 0 0 0-5-6.7"/></>,
    building: <><rect x="4" y="3" width="16" height="18" rx="1"/><path d="M9 7h2"/><path d="M13 7h2"/><path d="M9 11h2"/><path d="M13 11h2"/><path d="M9 15h2"/><path d="M13 15h2"/></>,
    folder: <><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></>,
    lock: <><rect x="4" y="11" width="16" height="10" rx="1.5"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></>,
    alert: <><path d="M12 3 2 21h20z"/><path d="M12 10v5"/><path d="M12 18h.01"/></>,
    info: <><circle cx="12" cy="12" r="9"/><path d="M12 8h.01"/><path d="M11 12h1v5h1"/></>,
    trash: <><path d="M3 6h18"/><path d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"/><path d="M19 6v13a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></>,
    download: <><path d="M12 4v12"/><path d="m7 11 5 5 5-5"/><path d="M4 20h16"/></>,
    paperclip: <><path d="m21 11.5-9 9a5 5 0 0 1-7-7l9-9a3.5 3.5 0 0 1 5 5l-9 9a2 2 0 0 1-3-3l8-8"/></>,
    quote: <><path d="M7 7h4v4H7z"/><path d="M7 11c0 3 0 5-3 6"/><path d="M14 7h4v4h-4z"/><path d="M14 11c0 3 0 5-3 6"/></>,
    book: <><path d="M4 4a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v16l-4-2-4 2-4-2-4 2z"/></>,
    sparkle: <><path d="M12 3v3"/><path d="M12 18v3"/><path d="M3 12h3"/><path d="M18 12h3"/><path d="m5.6 5.6 2.1 2.1"/><path d="m16.3 16.3 2.1 2.1"/><path d="m5.6 18.4 2.1-2.1"/><path d="m16.3 7.7 2.1-2.1"/></>,
    file_warn: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 12v3"/><path d="M12 18h.01"/></>,
    file_check: <><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="m9 15 2 2 4-4"/></>,
    cloud_up: <><path d="M16 16.5a4.5 4.5 0 0 0 .5-9 6 6 0 0 0-11.5 1.5 4 4 0 0 0 1 7.5"/><path d="M12 12v8"/><path d="m9 15 3-3 3 3"/></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></>,
  };
  return <svg {...common}>{paths[name] || null}</svg>;
};

// RABELIA logo block — monogram + wordmark
const RabeliaLogo = ({ size = "md" }) => {
  const dims = size === "lg"
    ? { box: 36, fs: 14, name: 16, sub: 11 }
    : size === "sm"
    ? { box: 24, fs: 10, name: 13, sub: 10 }
    : { box: 28, fs: 11, name: 14, sub: 10 };
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div className="rb-mono" style={{ width: dims.box, height: dims.box, fontSize: dims.fs }}>RB</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 1, lineHeight: 1.1 }}>
        <span style={{ fontWeight: 600, fontSize: dims.name, letterSpacing: "0.01em" }}>RABELIA</span>
        <span style={{ fontSize: dims.sub, color: "var(--fg-muted)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
          Cabinet d'avocats
        </span>
      </div>
    </div>
  );
};

// Document data — used across screens
const DOCS = [
  { name: "Contrat LogiTrans 2026.pdf", date: "12 mars 2026", size: "1.2 Mo", pages: 24 },
  { name: "Statuts SARL Mercier.pdf", date: "08 mars 2026", size: "480 Ko", pages: 8 },
  { name: "Bail commercial 14 rue Vaugirard.docx", date: "02 mars 2026", size: "320 Ko", pages: 12 },
  { name: "Jurisprudence Cass. com. 2024.pdf", date: "27 fév. 2026", size: "2.8 Mo", pages: 47 },
  { name: "Convention collective Syntec.pdf", date: "21 fév. 2026", size: "3.1 Mo", pages: 156 },
  { name: "Procès-verbal AG Mercier.pdf", date: "18 fév. 2026", size: "210 Ko", pages: 4 },
  { name: "Pacte d'associés ProTech SAS.pdf", date: "11 fév. 2026", size: "890 Ko", pages: 18 },
  { name: "Mémoire en défense Dossier 2025-114.docx", date: "04 fév. 2026", size: "640 Ko", pages: 22 },
  { name: "Contrat de cession parts sociales.pdf", date: "29 jan. 2026", size: "510 Ko", pages: 9 },
  { name: "Notes RGPD — audit interne.pdf", date: "22 jan. 2026", size: "1.8 Mo", pages: 31 },
  { name: "Conditions générales v3.2.pdf", date: "15 jan. 2026", size: "280 Ko", pages: 6 },
  { name: "Compromis de vente Levallois.pdf", date: "08 jan. 2026", size: "1.1 Mo", pages: 16 },
];

const CONVERSATIONS = [
  { title: "Clauses de non-concurrence LogiTrans", when: "Aujourd'hui" },
  { title: "Conditions de résiliation bail", when: "Aujourd'hui" },
  { title: "Délais préavis convention Syntec", when: "Hier" },
  { title: "Cession parts — agrément requis ?", when: "Hier" },
  { title: "Procédure AG extraordinaire", when: "21 mars" },
  { title: "Indemnité éviction commercial", when: "18 mars" },
  { title: "Régime fiscal apport en nature", when: "12 mars" },
];

// Expose globally
Object.assign(window, { Icon, RabeliaLogo, DOCS, CONVERSATIONS });
