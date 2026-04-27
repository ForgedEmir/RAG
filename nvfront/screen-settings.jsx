/* global React, Icon, RabeliaLogo, DOCS */

// =============================================================
// SCREEN 4 — SETTINGS
// =============================================================
const SettingsScreen = ({ tab = "workspace", showInviteModal = false, width = 1280, height = 820 }) => {
  return (
    <div className="rb-frame" style={{
      width, height,
      display: "grid", gridTemplateColumns: "260px 220px 1fr",
      background: "var(--bg-app)",
      borderRadius: 8, overflow: "hidden",
      border: "1px solid var(--border-default)",
      position: "relative",
    }}>
      <SettingsAppNav />
      <SettingsSubNav active={tab} />
      <SettingsContent tab={tab} />
      {showInviteModal && <InviteModal />}
    </div>
  );
};

const SettingsAppNav = () => (
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
        { name: "Importer", icon: "upload" },
        { name: "Paramètres", icon: "settings", active: true },
      ].map((it, i) => (
        <a key={i} className={"rb-listitem" + (it.active ? " rb-listitem--active" : "")}
           style={{ height: 32, padding: "0 10px", gap: 10 }}>
          <Icon name={it.icon} size={15} style={{ color: it.active ? "var(--accent)" : "var(--fg-secondary)" }} />
          <span className="rb-listitem__name">{it.name}</span>
        </a>
      ))}
    </nav>
    <div style={{ flex: 1 }} />
    <div style={{
      padding: "10px 12px",
      borderTop: "1px solid var(--border-subtle)",
      display: "flex", alignItems: "center", gap: 10,
    }}>
      <div className="rb-mono rb-mono--user">CM</div>
      <div style={{ flex: 1, lineHeight: 1.2 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>Claire Mercier</div>
        <div style={{ fontSize: 11, color: "var(--fg-muted)" }}>Administrateur</div>
      </div>
    </div>
  </aside>
);

const SettingsSubNav = ({ active }) => (
  <aside style={{
    background: "var(--bg-sunken)",
    borderRight: "1px solid var(--border-default)",
    padding: "20px 12px",
  }}>
    <div className="rb-section-label" style={{ padding: "0 10px", marginBottom: 8 }}>Paramètres</div>
    <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {[
        { id: "workspace", name: "Mon espace", icon: "building" },
        { id: "documents", name: "Documents", icon: "folder" },
        { id: "members", name: "Membres", icon: "users" },
      ].map((it) => (
        <a key={it.id} className={"rb-listitem" + (it.id === active ? " rb-listitem--active" : "")}
           style={{ height: 32, padding: "0 10px", gap: 10 }}>
          <Icon name={it.icon} size={15} style={{ color: it.id === active ? "var(--accent)" : "var(--fg-secondary)" }} />
          <span className="rb-listitem__name" style={{ fontWeight: it.id === active ? 500 : 400 }}>{it.name}</span>
        </a>
      ))}
    </nav>

    <div style={{
      marginTop: 24, padding: "0 10px",
      fontSize: 11, color: "var(--fg-muted)", lineHeight: 1.5,
    }}>
      Espace géré par RABELIA.<br />
      Plan Cabinet · 12 sièges
    </div>
  </aside>
);

const SettingsContent = ({ tab }) => (
  <main style={{ overflowY: "auto", display: "flex", flexDirection: "column" }} className="rb-scroll">
    <header style={{
      height: 56, padding: "0 32px",
      display: "flex", alignItems: "center",
      borderBottom: "1px solid var(--border-default)",
      background: "var(--bg-surface)",
    }}>
      <h1 style={{ fontSize: 15, fontWeight: 600, margin: 0 }}>
        {tab === "workspace" ? "Mon espace" : tab === "documents" ? "Documents indexés" : "Membres"}
      </h1>
    </header>
    <div style={{ flex: 1, padding: "28px 32px 100px", maxWidth: 880 }}>
      {tab === "workspace" && <WorkspacePane />}
      {tab === "documents" && <DocumentsPane />}
      {tab === "members" && <MembersPane />}
    </div>
    <AdminLockedZone />
  </main>
);

const ReadOnlyField = ({ label, value, mono }) => (
  <div>
    <div style={{ fontSize: 11.5, color: "var(--fg-muted)", marginBottom: 4, letterSpacing: "0.02em" }}>{label}</div>
    <div style={{
      fontSize: 13, color: "var(--fg-primary)",
      fontFamily: mono ? "var(--font-mono)" : "var(--font-sans)",
      padding: "8px 10px",
      background: "var(--bg-sunken)",
      border: "1px solid var(--border-subtle)",
      borderRadius: 4,
    }}>
      {value}
    </div>
  </div>
);

const WorkspacePane = () => (
  <>
    <div style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 13, fontWeight: 600, margin: "0 0 4px", letterSpacing: "0.02em" }}>Profil entreprise</h2>
      <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: 0 }}>
        Informations renseignées à la création du compte. Lecture seule.
      </p>
    </div>

    <div className="rb-card" style={{ padding: 24 }}>
      <div style={{ display: "flex", gap: 18, alignItems: "center", marginBottom: 24, paddingBottom: 24, borderBottom: "1px solid var(--border-subtle)" }}>
        <div className="rb-mono rb-mono--lg" style={{ width: 56, height: 56, fontSize: 18 }}>RB</div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 2 }}>RABELIA</div>
          <div style={{ fontSize: 12, color: "var(--fg-secondary)" }}>Cabinet d'avocats · Droit des affaires & contentieux commercial</div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <ReadOnlyField label="Raison sociale" value="RABELIA AARPI" />
        <ReadOnlyField label="SIRET" value="894 217 308 00012" mono />
        <ReadOnlyField label="Adresse" value="42 rue de Vaugirard, 75006 Paris" />
        <ReadOnlyField label="Numéro de Toque" value="P0421" mono />
        <ReadOnlyField label="Référent compte" value="Claire Mercier — Associée" />
        <ReadOnlyField label="Plan" value="Cabinet · 12 sièges · facturation annuelle" />
        <ReadOnlyField label="Identifiant espace" value="ws_rabelia_p0421" mono />
        <ReadOnlyField label="Région données" value="Paris (FR-1)" />
      </div>
    </div>

    <div style={{ marginTop: 16, fontSize: 12, color: "var(--fg-muted)", display: "flex", alignItems: "center", gap: 6 }}>
      <Icon name="info" size={13} />
      Pour modifier ces informations, contactez votre référent commercial RABELIA.
    </div>
  </>
);

const DocumentsPane = () => (
  <>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
      <div>
        <h2 style={{ fontSize: 13, fontWeight: 600, margin: "0 0 4px" }}>Documents indexés</h2>
        <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: 0 }}>
          {DOCS.length} documents · 13,4 Go utilisés sur 40 Go
        </p>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <div style={{ position: "relative" }}>
          <Icon name="search" size={14} style={{ position: "absolute", left: 10, top: 9, color: "var(--fg-muted)" }} />
          <input className="rb-input" placeholder="Rechercher…" style={{ paddingLeft: 32, width: 220 }} />
        </div>
        <button className="rb-btn rb-btn--primary" style={{ gap: 6 }}>
          <Icon name="plus" size={13} />
          <span>Importer</span>
        </button>
      </div>
    </div>

    <div className="rb-card" style={{ overflow: "hidden" }}>
      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(0,1fr) 130px 80px 100px 36px",
        padding: "10px 16px",
        background: "var(--bg-sunken)",
        borderBottom: "1px solid var(--border-default)",
        fontSize: 11, fontWeight: 600, letterSpacing: "0.04em",
        textTransform: "uppercase", color: "var(--fg-muted)",
      }}>
        <span>Nom</span>
        <span>Indexé le</span>
        <span style={{ textAlign: "right" }}>Pages</span>
        <span style={{ textAlign: "right" }}>Taille</span>
        <span></span>
      </div>
      {DOCS.map((d, i) => (
        <div key={i} style={{
          display: "grid",
          gridTemplateColumns: "minmax(0,1fr) 130px 80px 100px 36px",
          padding: "10px 16px",
          alignItems: "center",
          borderBottom: i < DOCS.length - 1 ? "1px solid var(--border-subtle)" : "none",
          fontSize: 13,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
            <Icon name="doc" size={15} style={{ color: "var(--fg-secondary)" }} />
            <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</span>
            <span className="rb-dot" />
          </div>
          <span style={{ color: "var(--fg-secondary)" }}>{d.date}</span>
          <span style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--fg-secondary)" }}>{d.pages}</span>
          <span style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: 11.5, color: "var(--fg-secondary)" }}>{d.size}</span>
          <button className="rb-btn rb-btn--ghost" style={{ width: 24, height: 24, padding: 0, justifySelf: "end" }}>
            <Icon name="trash" size={13} />
          </button>
        </div>
      ))}
    </div>
  </>
);

const MEMBERS = [
  { name: "Claire Mercier", email: "claire.mercier@rabelia.fr", role: "Administrateur", status: "active", since: "12 jan. 2026", initials: "CM" },
  { name: "Antoine Beaufort", email: "a.beaufort@rabelia.fr", role: "Avocat associé", status: "active", since: "12 jan. 2026", initials: "AB" },
  { name: "Hélène Dussart", email: "h.dussart@rabelia.fr", role: "Avocat collaborateur", status: "active", since: "18 jan. 2026", initials: "HD" },
  { name: "Maxime Roussel", email: "m.roussel@rabelia.fr", role: "Avocat collaborateur", status: "active", since: "02 fév. 2026", initials: "MR" },
  { name: "Sophie Leclerc", email: "s.leclerc@rabelia.fr", role: "Juriste", status: "active", since: "14 fév. 2026", initials: "SL" },
  { name: "Julien Pernaud", email: "j.pernaud@rabelia.fr", role: "Avocat collaborateur", status: "invited", since: "Invitation envoyée le 21 mars", initials: "JP" },
  { name: "Inès Caillaux", email: "i.caillaux@rabelia.fr", role: "Assistante juridique", status: "invited", since: "Invitation envoyée le 23 mars", initials: "IC" },
];

const MembersPane = () => (
  <>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
      <div>
        <h2 style={{ fontSize: 13, fontWeight: 600, margin: "0 0 4px" }}>Membres de l'espace</h2>
        <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: 0 }}>
          5 membres actifs · 2 invitations en attente · 5 sièges disponibles
        </p>
      </div>
      <button className="rb-btn rb-btn--primary" style={{ gap: 6 }}>
        <Icon name="plus" size={13} />
        <span>Inviter un membre</span>
      </button>
    </div>

    <div className="rb-card" style={{ overflow: "hidden" }}>
      {MEMBERS.map((m, i) => (
        <div key={i} style={{
          display: "grid",
          gridTemplateColumns: "auto 1fr 200px 140px 36px",
          gap: 14, alignItems: "center",
          padding: "12px 16px",
          borderBottom: i < MEMBERS.length - 1 ? "1px solid var(--border-subtle)" : "none",
        }}>
          <div className="rb-mono rb-mono--user" style={{ width: 32, height: 32, fontSize: 11 }}>{m.initials}</div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 1 }}>{m.name}</div>
            <div style={{ fontSize: 11.5, color: "var(--fg-muted)", fontFamily: "var(--font-mono)" }}>{m.email}</div>
          </div>
          <div style={{ fontSize: 12.5, color: "var(--fg-secondary)" }}>{m.role}</div>
          <div>
            {m.status === "active" ? (
              <span className="rb-pill rb-pill--ok"><span className="rb-dot" />Actif</span>
            ) : (
              <span className="rb-pill rb-pill--warn">Invitation envoyée</span>
            )}
            <div style={{ fontSize: 10.5, color: "var(--fg-muted)", marginTop: 3 }}>{m.since}</div>
          </div>
          <button className="rb-btn rb-btn--ghost" style={{ width: 28, height: 28, padding: 0 }}>
            <Icon name="chevron_right" size={14} />
          </button>
        </div>
      ))}
    </div>
  </>
);

const AdminLockedZone = () => (
  <div style={{
    margin: "0 32px 28px",
    background: "var(--bg-sunken)",
    border: "1px dashed var(--border-strong)",
    borderRadius: 8,
    padding: "18px 20px",
    display: "flex", gap: 14, alignItems: "flex-start",
    maxWidth: 880,
  }}>
    <Icon name="lock" size={18} style={{ color: "var(--fg-muted)", marginTop: 2 }} />
    <div style={{ flex: 1 }}>
      <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4, color: "var(--fg-secondary)" }}>
        Actions réservées à l'administrateur système
      </div>
      <p style={{ fontSize: 12, color: "var(--fg-muted)", margin: "0 0 12px", lineHeight: 1.55 }}>
        Suppression d'espace, rotation des clés de chiffrement, export complet et réinitialisation
        de l'index vectoriel. Ces opérations sont gérées par l'équipe RABELIA — contactez votre
        référent compte pour toute demande.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {["Réinitialiser l'index", "Rotation des clés", "Export complet", "Supprimer l'espace"].map((a, i) => (
          <button key={i} className="rb-btn rb-btn--secondary rb-btn--disabled" disabled
            style={{ background: "transparent", color: "var(--fg-disabled)", fontSize: 12 }}>
            <Icon name="lock" size={12} />
            <span>{a}</span>
          </button>
        ))}
      </div>
    </div>
  </div>
);

// =============================================================
// EXTRA STATE — INVITE MEMBER MODAL
// =============================================================
const InviteModal = () => (
  <div style={{
    position: "absolute", inset: 0,
    background: "rgba(15, 26, 43, 0.32)",
    display: "flex", alignItems: "center", justifyContent: "center",
    zIndex: 10,
  }}>
    <div style={{
      width: 460, background: "var(--bg-surface)",
      borderRadius: 8, boxShadow: "var(--shadow-pop)",
      overflow: "hidden",
    }}>
      <div style={{
        padding: "16px 20px",
        borderBottom: "1px solid var(--border-subtle)",
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Inviter un membre</h3>
        <button className="rb-btn rb-btn--ghost" style={{ width: 26, height: 26, padding: 0 }}>
          <Icon name="x" size={14} />
        </button>
      </div>
      <div style={{ padding: "20px" }}>
        <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: "0 0 18px", lineHeight: 1.55 }}>
          Le membre recevra un email avec un lien de connexion personnel.
          Il accédera aux mêmes documents que vous.
        </p>

        <div style={{ marginBottom: 14 }}>
          <label className="rb-label">Adresse email</label>
          <input className="rb-input" placeholder="prenom.nom@rabelia.fr" defaultValue="j.pernaud@rabelia.fr" />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
          <div>
            <label className="rb-label">Prénom</label>
            <input className="rb-input" defaultValue="Julien" />
          </div>
          <div>
            <label className="rb-label">Nom</label>
            <input className="rb-input" defaultValue="Pernaud" />
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label className="rb-label">Rôle</label>
          <div style={{
            border: "1px solid var(--border-default)", borderRadius: 6,
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0 10px", height: 32, fontSize: 13,
          }}>
            <span>Avocat collaborateur</span>
            <Icon name="chevron_down" size={14} style={{ color: "var(--fg-muted)" }} />
          </div>
        </div>

        <div style={{
          background: "var(--bg-sunken)",
          padding: "10px 12px", borderRadius: 4,
          fontSize: 11.5, color: "var(--fg-secondary)",
          display: "flex", gap: 8, alignItems: "flex-start",
        }}>
          <Icon name="info" size={13} style={{ marginTop: 1, flex: "none" }} />
          <span>5 sièges restants sur votre plan Cabinet (12 sièges).</span>
        </div>
      </div>
      <div style={{
        padding: "12px 20px",
        borderTop: "1px solid var(--border-subtle)",
        background: "var(--bg-sunken)",
        display: "flex", justifyContent: "flex-end", gap: 8,
      }}>
        <button className="rb-btn rb-btn--secondary">Annuler</button>
        <button className="rb-btn rb-btn--primary">Envoyer l'invitation</button>
      </div>
    </div>
  </div>
);

Object.assign(window, { SettingsScreen, InviteModal });
