/* global React, Icon, RabeliaLogo */

// =============================================================
// SCREEN 1 — LOGIN
// =============================================================
const LoginScreen = ({ width = 1280, height = 820 }) => (
  <div className="rb-frame" style={{
    width, height,
    display: "flex", alignItems: "center", justifyContent: "center",
    background: "var(--bg-app)",
    borderRadius: 8, overflow: "hidden",
    border: "1px solid var(--border-default)",
    position: "relative",
  }}>
    {/* corner mark — sober software-like */}
    <div style={{
      position: "absolute", top: 24, left: 28,
      fontSize: 11, color: "var(--fg-muted)",
      letterSpacing: "0.08em", textTransform: "uppercase",
      fontFamily: "var(--font-mono)",
    }}>
      Portail client · v2.4
    </div>
    <div style={{
      position: "absolute", bottom: 24, left: 28, right: 28,
      display: "flex", justifyContent: "space-between",
      fontSize: 11, color: "var(--fg-muted)",
    }}>
      <span>© RABELIA 2026</span>
      <span>support@rabelia.fr · +33 1 84 80 12 00</span>
    </div>

    <div style={{ width: 380, textAlign: "center" }}>
      <div style={{ display: "flex", justifyContent: "center", marginBottom: 28 }}>
        <RabeliaLogo size="lg" />
      </div>

      <h1 style={{
        fontSize: 22, fontWeight: 600, margin: "0 0 8px",
        letterSpacing: "-0.015em",
      }}>
        Connexion à votre espace
      </h1>
      <p style={{
        fontSize: 13, color: "var(--fg-secondary)", margin: "0 0 32px",
        lineHeight: 1.55,
      }}>
        Saisissez votre adresse professionnelle.<br />
        Un lien de connexion vous sera envoyé.
      </p>

      <form style={{ textAlign: "left" }} onSubmit={(e) => e.preventDefault()}>
        <label className="rb-label" htmlFor="login-email">Adresse email</label>
        <input
          id="login-email"
          className="rb-input rb-input--lg"
          type="email"
          defaultValue="claire.mercier@rabelia.fr"
          placeholder="vous@rabelia.fr"
          autoComplete="email"
        />
        <button type="submit" className="rb-btn rb-btn--primary rb-btn--lg rb-btn--block" style={{ marginTop: 16 }}>
          Recevoir un lien de connexion
        </button>
      </form>

      <p style={{
        fontSize: 11.5, color: "var(--fg-muted)", margin: "24px 0 0",
        lineHeight: 1.5,
      }}>
        Accès réservé aux collaborateurs autorisés.<br />
        En cas de difficulté, contactez votre administrateur interne.
      </p>
    </div>
  </div>
);

// =============================================================
// SCREEN 3 — UPLOAD
// =============================================================
const UploadScreen = ({ state = "drop", width = 1280, height = 820 }) => {
  // states: "drop" | "progress" | "done" | "error"
  return (
    <div className="rb-frame" style={{
      width, height,
      display: "grid", gridTemplateColumns: "260px 1fr",
      background: "var(--bg-app)",
      borderRadius: 8, overflow: "hidden",
      border: "1px solid var(--border-default)",
    }}>
      <UploadSidebar />
      <div style={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
        <header style={{
          height: 56, padding: "0 24px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          borderBottom: "1px solid var(--border-default)",
          background: "var(--bg-surface)",
        }}>
          <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Importer des documents</h1>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <span style={{ fontSize: 12, color: "var(--fg-muted)" }}>
              Formats acceptés : PDF, DOCX, TXT · 50 Mo max
            </span>
          </div>
        </header>
        <div style={{ flex: 1, padding: 32, overflowY: "auto" }} className="rb-scroll">
          <div style={{ maxWidth: 720, margin: "0 auto" }}>
            {state === "drop" && <DropZone />}
            {state === "progress" && <ProgressView />}
            {state === "done" && <DoneView />}
            {state === "error" && <ErrorView />}
          </div>
        </div>
      </div>
    </div>
  );
};

const UploadSidebar = () => (
  <aside style={{
    background: "var(--bg-surface)",
    borderRight: "1px solid var(--border-default)",
    display: "flex", flexDirection: "column",
  }}>
    <div style={{ padding: "16px 14px 14px", borderBottom: "1px solid var(--border-subtle)" }}>
      <RabeliaLogo size="md" />
    </div>
    <nav style={{ padding: 12, display: "flex", flexDirection: "column", gap: 2 }}>
      {[
        { name: "Conversations", icon: "chat" },
        { name: "Importer", icon: "upload", active: true },
        { name: "Paramètres", icon: "settings" },
      ].map((it, i) => (
        <a key={i} className={"rb-listitem" + (it.active ? " rb-listitem--active" : "")}
           style={{ height: 32, padding: "0 10px", gap: 10 }}>
          <Icon name={it.icon} size={15} style={{ color: it.active ? "var(--accent)" : "var(--fg-secondary)" }} />
          <span className="rb-listitem__name">{it.name}</span>
        </a>
      ))}
    </nav>
    <div style={{ flex: 1 }} />
    <div style={{ padding: 14, borderTop: "1px solid var(--border-subtle)", fontSize: 11.5, color: "var(--fg-muted)", lineHeight: 1.5 }}>
      <div style={{ fontWeight: 500, color: "var(--fg-secondary)", marginBottom: 4 }}>Espace utilisé</div>
      <div style={{ height: 4, background: "var(--bg-muted)", borderRadius: 2, marginBottom: 4 }}>
        <div style={{ width: "34%", height: "100%", background: "var(--accent)", borderRadius: 2 }} />
      </div>
      <div style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>13,4 / 40 Go</div>
    </div>
  </aside>
);

const DropZone = () => (
  <>
    <div style={{
      border: "1.5px dashed var(--border-strong)",
      borderRadius: 8,
      background: "var(--bg-surface)",
      padding: "64px 32px",
      textAlign: "center",
    }}>
      <div style={{
        width: 56, height: 56, borderRadius: 10,
        background: "var(--accent-soft)", color: "var(--accent)",
        display: "flex", alignItems: "center", justifyContent: "center",
        margin: "0 auto 18px",
      }}>
        <Icon name="cloud_up" size={26} />
      </div>
      <h2 style={{ fontSize: 16, fontWeight: 600, margin: "0 0 6px" }}>
        Déposez vos documents ici
      </h2>
      <p style={{ fontSize: 13, color: "var(--fg-secondary)", margin: "0 0 18px" }}>
        ou parcourez votre poste pour les sélectionner
      </p>
      <button className="rb-btn rb-btn--primary">Parcourir les fichiers</button>
      <div style={{ marginTop: 24, fontSize: 11.5, color: "var(--fg-muted)", fontFamily: "var(--font-mono)" }}>
        PDF · DOCX · TXT — 50 Mo par fichier
      </div>
    </div>

    <div style={{ marginTop: 24, fontSize: 12, color: "var(--fg-secondary)", lineHeight: 1.55, padding: "0 4px" }}>
      <div style={{ fontWeight: 500, color: "var(--fg-primary)", marginBottom: 6 }}>À propos de l'indexation</div>
      Les documents sont chiffrés au dépôt et indexés en local sur votre instance dédiée.
      L'extraction du texte et la création de l'index vectoriel prennent en moyenne
      40 secondes par tranche de 100 pages.
    </div>
  </>
);

const ProgressView = () => {
  const files = [
    { name: "Convention collective Syntec.pdf", pct: 100, state: "done" },
    { name: "Pacte d'associés ProTech SAS.pdf", pct: 72, state: "indexing" },
    { name: "Mémoire en défense Dossier 2025-114.docx", pct: 38, state: "indexing" },
    { name: "Notes RGPD — audit interne.pdf", pct: 0, state: "queued" },
  ];
  return (
    <div className="rb-card" style={{ padding: 24 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4 }}>
        <h2 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>Indexation en cours</h2>
        <span style={{ fontSize: 12, color: "var(--fg-muted)", fontFamily: "var(--font-mono)" }}>
          2 / 4 fichiers · ~ 1 min 20 s restantes
        </span>
      </div>
      <p style={{ margin: "0 0 18px", fontSize: 12.5, color: "var(--fg-secondary)" }}>
        Vous pouvez fermer cette page — l'indexation continue en arrière-plan.
      </p>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {files.map((f, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <Icon
              name={f.state === "done" ? "file_check" : "doc"}
              size={18}
              style={{ color: f.state === "done" ? "var(--ok)" : "var(--fg-secondary)" }}
            />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                <span style={{ fontSize: 13, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {f.name}
                </span>
                <span style={{ fontSize: 11.5, color: "var(--fg-muted)", fontFamily: "var(--font-mono)" }}>
                  {f.state === "queued" ? "en attente" : f.state === "done" ? "indexé" : `${f.pct} %`}
                </span>
              </div>
              <div style={{ height: 4, background: "var(--bg-muted)", borderRadius: 2, overflow: "hidden" }}>
                <div style={{
                  width: `${f.pct}%`, height: "100%",
                  background: f.state === "done" ? "var(--ok)" : "var(--accent)",
                  borderRadius: 2,
                }} />
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const DoneView = () => (
  <div className="rb-card" style={{ padding: "40px 32px", textAlign: "center" }}>
    <div style={{
      width: 48, height: 48, borderRadius: "50%",
      background: "var(--ok-soft)", color: "var(--ok)",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      marginBottom: 18,
    }}>
      <Icon name="check" size={22} />
    </div>
    <h2 style={{ fontSize: 18, fontWeight: 600, margin: "0 0 6px" }}>Documents prêts</h2>
    <p style={{ fontSize: 13, color: "var(--fg-secondary)", margin: "0 0 24px" }}>
      4 documents ont été indexés et sont désormais interrogeables depuis l'assistant.
    </p>
    <div style={{ display: "flex", justifyContent: "center", gap: 8 }}>
      <button className="rb-btn rb-btn--primary">Ouvrir l'assistant</button>
      <button className="rb-btn rb-btn--secondary">Importer d'autres fichiers</button>
    </div>

    <div style={{
      marginTop: 32, paddingTop: 20,
      borderTop: "1px solid var(--border-subtle)",
      textAlign: "left",
    }}>
      <div className="rb-section-label" style={{ padding: 0, marginBottom: 10 }}>Récapitulatif</div>
      {[
        { name: "Convention collective Syntec.pdf", pages: 156 },
        { name: "Pacte d'associés ProTech SAS.pdf", pages: 18 },
        { name: "Mémoire en défense Dossier 2025-114.docx", pages: 22 },
        { name: "Notes RGPD — audit interne.pdf", pages: 31 },
      ].map((f, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "8px 0", borderBottom: i < 3 ? "1px solid var(--border-subtle)" : "none",
          fontSize: 13,
        }}>
          <Icon name="file_check" size={16} style={{ color: "var(--ok)" }} />
          <span style={{ flex: 1 }}>{f.name}</span>
          <span style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--fg-muted)" }}>
            {f.pages} p. · indexé
          </span>
        </div>
      ))}
    </div>
  </div>
);

const ErrorView = () => (
  <div className="rb-card" style={{ padding: 0, overflow: "hidden" }}>
    <div style={{
      padding: "20px 24px",
      background: "var(--danger-soft)",
      borderBottom: "1px solid var(--border-default)",
      display: "flex", gap: 14, alignItems: "flex-start",
    }}>
      <div style={{
        width: 32, height: 32, borderRadius: 6,
        background: "#fff", color: "var(--danger)",
        display: "flex", alignItems: "center", justifyContent: "center",
        flex: "none",
      }}>
        <Icon name="alert" size={18} />
      </div>
      <div style={{ flex: 1 }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, margin: "0 0 4px", color: "var(--danger)" }}>
          1 fichier n'a pas pu être importé
        </h2>
        <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: 0, lineHeight: 1.5 }}>
          Les autres fichiers ont été indexés normalement.
          Vérifiez le format ou la taille du fichier rejeté.
        </p>
      </div>
    </div>

    <div style={{ padding: "12px 24px" }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "12px 0",
      }}>
        <Icon name="file_warn" size={20} style={{ color: "var(--danger)" }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500 }}>Plaidoirie audience 14-03.zip</div>
          <div style={{ fontSize: 11.5, color: "var(--fg-muted)", fontFamily: "var(--font-mono)" }}>
            Format .zip non supporté · 12,4 Mo
          </div>
        </div>
        <button className="rb-btn rb-btn--ghost" style={{ color: "var(--danger)" }}>
          <Icon name="trash" size={14} />
        </button>
      </div>

      <hr className="rb-divider" />

      {["Contrat cession parts.pdf", "Compromis de vente Levallois.pdf"].map((n, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "center", gap: 12, padding: "12px 0",
          borderBottom: i < 1 ? "1px solid var(--border-subtle)" : "none",
        }}>
          <Icon name="file_check" size={20} style={{ color: "var(--ok)" }} />
          <div style={{ flex: 1, fontSize: 13 }}>{n}</div>
          <span className="rb-pill rb-pill--ok"><span className="rb-dot" />indexé</span>
        </div>
      ))}
    </div>

    <div style={{
      padding: "14px 24px",
      borderTop: "1px solid var(--border-subtle)",
      background: "var(--bg-sunken)",
      display: "flex", justifyContent: "space-between", alignItems: "center",
    }}>
      <span style={{ fontSize: 12, color: "var(--fg-secondary)" }}>
        Convertissez le fichier en PDF, DOCX ou TXT puis ré-importez-le.
      </span>
      <div style={{ display: "flex", gap: 8 }}>
        <button className="rb-btn rb-btn--secondary">Réessayer</button>
        <button className="rb-btn rb-btn--primary">Continuer</button>
      </div>
    </div>
  </div>
);

Object.assign(window, { LoginScreen, UploadScreen });
