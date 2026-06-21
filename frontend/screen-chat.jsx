/* global React, Icon, RabeliaLogo, DOCS, CONVERSATIONS */

// =============================================================
// SCREEN 2 — CHAT (priority screen)
// =============================================================
const ChatScreen = ({ empty = false, width = 1280, height = 820 }) => {
  return (
    <div
      className="rb-frame"
      style={{
        width, height, display: "grid",
        gridTemplateColumns: "260px 1fr",
        background: "var(--bg-app)",
        borderRadius: 8, overflow: "hidden",
        border: "1px solid var(--border-default)",
      }}
    >
      <ChatSidebar activeConv={empty ? null : 0} />
      <ChatMain empty={empty} />
    </div>
  );
};

const ChatSidebar = ({ activeConv }) => (
  <aside style={{
    background: "var(--bg-surface)",
    borderRight: "1px solid var(--border-default)",
    display: "flex", flexDirection: "column",
    minHeight: 0,
  }}>
    {/* Logo */}
    <div style={{ padding: "16px 14px 14px", borderBottom: "1px solid var(--border-subtle)" }}>
      <RabeliaLogo size="md" />
    </div>

    {/* New chat button */}
    <div style={{ padding: "12px 12px 8px" }}>
      <button className="rb-btn rb-btn--secondary rb-btn--block" style={{ justifyContent: "flex-start", gap: 8 }}>
        <Icon name="plus" size={14} />
        <span>Nouvelle conversation</span>
      </button>
    </div>

    {/* Documents */}
    <div className="rb-scroll" style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "8px 8px 12px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 8px 6px" }}>
        <span className="rb-section-label" style={{ padding: 0 }}>Documents indexed</span>
        <span style={{ fontSize: 10.5, color: "var(--fg-muted)", fontFamily: "var(--font-mono)" }}>{DOCS.length}</span>
      </div>
      {DOCS.slice(0, 12).map((d, i) => (
        <div key={i} className="rb-listitem">
          <span className="rb-dot" title="Indexed" />
          <span className="rb-listitem__name" title={d.name}>{d.name}</span>
        </div>
      ))}

      <div style={{ height: 16 }} />

      <div style={{ padding: "10px 8px 6px" }}>
        <span className="rb-section-label" style={{ padding: 0 }}>Conversations</span>
      </div>
      {CONVERSATIONS.map((c, i) => (
        <div key={i} className={"rb-listitem" + (i === activeConv ? " rb-listitem--active" : "")}>
          <span className="rb-listitem__name">{c.title}</span>
          <span className="rb-listitem__meta">{c.when}</span>
        </div>
      ))}
    </div>

    {/* User avatar */}
    <div style={{
      padding: "10px 12px",
      borderTop: "1px solid var(--border-subtle)",
      display: "flex", alignItems: "center", gap: 10,
    }}>
      <div className="rb-mono rb-mono--user">CM</div>
      <div style={{ flex: 1, minWidth: 0, lineHeight: 1.2 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Claire Mercier</div>
        <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>Partner · Droit des affaires</div>
      </div>
      <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }} aria-label="Settings">
        <Icon name="settings" size={14} />
      </button>
    </div>
  </aside>
);

const ChatMain = ({ empty }) => (
  <main style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
    {/* Topbar */}
    <header style={{
      height: 56, padding: "0 24px",
      display: "flex", alignItems: "center", justifyContent: "space-between",
      borderBottom: "1px solid var(--border-default)",
      background: "var(--bg-surface)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0, letterSpacing: "-0.01em" }}>
          Assistant documentaire
        </h1>
        <span className="rb-pill rb-pill--ok">
          <span className="rb-dot" />
          {DOCS.length} documents indexed
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <button className="rb-btn rb-btn--ghost" style={{ gap: 6 }}>
          <Icon name="upload" size={14} />
          <span>Importer</span>
        </button>
        <button className="rb-btn rb-btn--ghost" style={{ gap: 6 }}>
          <Icon name="settings" size={14} />
          <span>Settings</span>
        </button>
      </div>
    </header>

    {/* Conversation area */}
    <div className="rb-scroll" style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "32px 0" }}>
      {empty ? <ChatEmptyState /> : <ChatTranscript />}
    </div>

    {/* Composer */}
    <div style={{
      borderTop: "1px solid var(--border-default)",
      background: "var(--bg-surface)",
      padding: "16px 24px 20px",
    }}>
      <div style={{ maxWidth: 760, margin: "0 auto" }}>
        <Composer />
        <div style={{
          marginTop: 8, fontSize: 11, color: "var(--fg-muted)",
          display: "flex", justifyContent: "space-between",
        }}>
          <span>Responses cite passages from indexed documents.</span>
          <span style={{ fontFamily: "var(--font-mono)" }}>↵ pour envoyer · ⇧↵ saut de ligne</span>
        </div>
      </div>
    </div>
  </main>
);

const Composer = ({ value = "" }) => (
  <div style={{
    display: "flex", alignItems: "flex-end", gap: 8,
    padding: 8,
    background: "var(--bg-surface)",
    border: "1px solid var(--border-strong)",
    borderRadius: 10,
    boxShadow: "var(--shadow-1)",
  }}>
    <button className="rb-btn rb-btn--ghost" style={{ width: 32, height: 32, padding: 0 }} aria-label="Joindre">
      <Icon name="paperclip" size={15} />
    </button>
    <div style={{
      flex: 1, minHeight: 32, padding: "8px 4px",
      fontSize: 14, color: value ? "var(--fg-primary)" : "var(--fg-disabled)",
    }}>
      {value || "Posez votre question sur les documents indexed…"}
    </div>
    <button className="rb-btn rb-btn--primary" style={{ width: 32, height: 32, padding: 0 }} aria-label="Envoyer">
      <Icon name="send" size={14} />
    </button>
  </div>
);

const ChatEmptyState = () => (
  <div style={{
    maxWidth: 720, margin: "0 auto", padding: "60px 24px",
    textAlign: "left",
  }}>
    <div style={{
      width: 44, height: 44, borderRadius: 8,
      background: "var(--accent-soft)", color: "var(--accent)",
      display: "flex", alignItems: "center", justifyContent: "center",
      marginBottom: 20,
    }}>
      <Icon name="sparkle" size={20} />
    </div>
    <h2 style={{ fontSize: 22, fontWeight: 600, margin: "0 0 8px", letterSpacing: "-0.015em" }}>
      Bonjour Claire.
    </h2>
    <p style={{ fontSize: 14, color: "var(--fg-secondary)", margin: "0 0 28px", maxWidth: 540, lineHeight: 1.55 }}>
      Your {DOCS.length} documents are indexed and ready to query. Ask a question
      in natural language — each response links back to the cited source passages.
    </p>

    <div className="rb-section-label" style={{ padding: 0, marginBottom: 10 }}>Suggestions</div>
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
      {[
        "Quelles sont les clauses de non-concurrence dans le contrat LogiTrans ?",
        "What is the notice period for terminating the Vaugirard lease?",
        "Summarize the ProTech SAS shareholders' agreement in 5 points.",
        "Quels documents traitent de la cession de parts sociales ?",
      ].map((s, i) => (
        <button key={i} style={{
          textAlign: "left", padding: "12px 14px",
          background: "var(--bg-surface)",
          border: "1px solid var(--border-default)",
          borderRadius: 6, cursor: "pointer",
          fontSize: 13, color: "var(--fg-primary)",
          fontFamily: "var(--font-sans)",
          lineHeight: 1.4,
        }}>{s}</button>
      ))}
    </div>
  </div>
);

const ChatTranscript = () => (
  <div style={{ maxWidth: 760, margin: "0 auto", padding: "0 24px", display: "flex", flexDirection: "column", gap: 28 }}>
    <UserMsg text="What are the non-compete clauses in the LogiTrans contract, and how long do they apply?" />

    <AIMsg
      paragraphs={[
        "Le contrat LogiTrans 2026 contient deux clauses de non-concurrence distinctes.",
        "The first (§8.2) binds the executive for 24 months after leaving office, across the European Union, with financial compensation equal to 30% of gross annual salary. The second (§12.4) applies to senior employees and provides for a shorter 12-month term limited to French territory.",
        "Both clauses comply with the Cass. com. 2024 case law you have indexed — notably the ruling of 14 March 2024 confirming the requirements of geographic proportionality and financial consideration.",
      ]}
      cites={[
        { doc: "Contrat LogiTrans 2026", loc: "§8.2 · p. 14" },
        { doc: "Contrat LogiTrans 2026", loc: "§12.4 · p. 19" },
        { doc: "Jurisprudence Cass. com.", loc: "ruling 14/03/24" },
      ]}
    />

    <UserMsg text="Is the 30% consideration sufficient in light of recent case law?" />

    <AIMsg
      paragraphs={[
        "Yes. The Court of Cassation holds that compensation between 25% and 33% of salary is valid provided it is paid monthly and does not depend on the grounds for termination.",
        "In the LogiTrans contract, the wording of §8.2 satisfies both conditions: payment is monthly and the clause applies 'regardless of the grounds for termination'.",
      ]}
      cites={[
        { doc: "Jurisprudence Cass. com.", loc: "p. 22-24" },
        { doc: "Contrat LogiTrans 2026", loc: "§8.2 al. 3" },
      ]}
    />
  </div>
);

const UserMsg = ({ text }) => (
  <div style={{ display: "flex", justifyContent: "flex-end" }}>
    <div style={{
      maxWidth: "78%",
      padding: "10px 14px",
      background: "var(--accent)",
      color: "var(--fg-inverse)",
      borderRadius: "10px 10px 2px 10px",
      fontSize: 14, lineHeight: 1.5,
    }}>{text}</div>
  </div>
);

const AIMsg = ({ paragraphs, cites }) => (
  <div style={{ display: "flex", gap: 12 }}>
    <div style={{
      width: 28, height: 28, borderRadius: 6,
      background: "var(--bg-muted)", color: "var(--fg-secondary)",
      display: "flex", alignItems: "center", justifyContent: "center",
      flex: "none", marginTop: 2,
    }}>
      <Icon name="sparkle" size={14} />
    </div>
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 11.5, color: "var(--fg-muted)", marginBottom: 6, letterSpacing: "0.02em" }}>
        Assistant · from 3 documents
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {paragraphs.map((p, i) => (
          <p key={i} style={{ margin: 0, fontSize: 14, lineHeight: 1.6, color: "var(--fg-primary)" }}>{p}</p>
        ))}
      </div>
      <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 6 }}>
        {cites.map((c, i) => (
          <span key={i} className="rb-cite">
            <span className="rb-cite__doc">{c.doc}</span>
            <span className="rb-cite__loc">{c.loc}</span>
          </span>
        ))}
      </div>
    </div>
  </div>
);

Object.assign(window, { ChatScreen });
