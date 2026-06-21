/* global React, Icon, RabeliaLogo, DOCS */

// =============================================================
// SCREEN 4 — SETTINGS
// =============================================================
const SettingsScreen = ({ tab = "workspace", showInviteMBdal = false, width = 1280, height = 820 }) => {
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
      {showInviteMBdal && <InviteMBdal />}
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
        { name: "Settings", icon: "settings", active: true },
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
    <div className="rb-section-label" style={{ padding: "0 10px", marginBottom: 8 }}>Settings</div>
    <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      {[
        { id: "workspace", name: "My workspace", icon: "building" },
        { id: "documents", name: "Documents", icon: "folder" },
        { id: "members", name: "Members", icon: "users" },
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
      Workspace managed by RABELIA.<br />
      Firm Plan · 12 seats
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
        {tab === "workspace" ? "My workspace" : tab === "documents" ? "Documents indexed" : "Members"}
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
        Information provided at account creation. Read-only.
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
        <ReadOnlyField label="Toque Number" value="P0421" mono />
        <ReadOnlyField label="Account Referent" value="Claire Mercier — Partner" />
        <ReadOnlyField label="Plan" value="Cabinet · 12 seats · annual billing" />
        <ReadOnlyField label="Identifiant espace" value="ws_rabelia_p0421" mono />
        <ReadOnlyField label="Data Region" value="Paris (FR-1)" />
      </div>
    </div>

    <div style={{ marginTop: 16, fontSize: 12, color: "var(--fg-muted)", display: "flex", alignItems: "center", gap: 6 }}>
      <Icon name="info" size={13} />
      To modify this information, contact your RABELIA sales representative.
    </div>
  </>
);

const DocumentsPane = () => (
  <>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
      <div>
        <h2 style={{ fontSize: 13, fontWeight: 600, margin: "0 0 4px" }}>Documents indexed</h2>
        <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: 0 }}>
          {DOCS.length} documents · 13.4 GB used of 40 GB
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
        <span>Indexed on</span>
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
  { name: "Claire Mercier", email: "claire.mercier@rabelia.fr", role: "Administrator", status: "active", since: "12 Jan. 2026", initials: "CM" },
  { name: "Antoine Beaufort", email: "a.beaufort@rabelia.fr", role: "Partner Lawyer", status: "active", since: "12 Jan. 2026", initials: "AB" },
  { name: "Helene Dussart", email: "h.dussart@rabelia.fr", role: "Associate Lawyer", status: "active", since: "18 Jan. 2026", initials: "HD" },
  { name: "Maxime Roussel", email: "m.roussel@rabelia.fr", role: "Associate Lawyer", status: "active", since: "02 Feb. 2026", initials: "MR" },
  { name: "Sophie Leclerc", email: "s.leclerc@rabelia.fr", role: "Legal Counsel", status: "active", since: "14 Feb. 2026", initials: "SL" },
  { name: "Julien Pernaud", email: "j.pernaud@rabelia.fr", role: "Associate Lawyer", status: "invited", since: "Invitation sent on 21 March", initials: "JP" },
  { name: "Ines Caillaux", email: "i.caillaux@rabelia.fr", role: "Legal Assistant", status: "invited", since: "Invitation sent on 23 March", initials: "IC" },
];

const MembersPane = () => (
  <>
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 16 }}>
      <div>
        <h2 style={{ fontSize: 13, fontWeight: 600, margin: "0 0 4px" }}>Members de l'espace</h2>
        <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: 0 }}>
          5 active members · 2 invitations queued · 5 seats available
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
              <span className="rb-pill rb-pill--warn">Invitation sent</span>
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
        Actions reserved for the system administrator
      </div>
      <p style={{ fontSize: 12, color: "var(--fg-muted)", margin: "0 0 12px", lineHeight: 1.55 }}>
        Workspace deletion, encryption key rotation, full export, and vector index reset.
        These operations are managed by the RABELIA team — contact your account owner for any request.
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {["Reset index", "Key rotation", "Full export", "Delete workspace"].map((a, i) => (
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
const InviteMBdal = () => (
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
        <h3 style={{ fontSize: 14, fontWeight: 600, margin: 0 }}>Invite a member</h3>
        <button className="rb-btn rb-btn--ghost" style={{ width: 26, height: 26, padding: 0 }}>
          <Icon name="x" size={14} />
        </button>
      </div>
      <div style={{ padding: "20px" }}>
        <p style={{ fontSize: 12.5, color: "var(--fg-secondary)", margin: "0 0 18px", lineHeight: 1.55 }}>
          The member will receive an email with a personal sign-in link.
          They will have access to the same documents as you.
        </p>

        <div style={{ marginBottom: 14 }}>
          <label className="rb-label">Adresse email</label>
          <input className="rb-input" placeholder="prenom.nom@rabelia.fr" defaultValue="j.pernaud@rabelia.fr" />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 14 }}>
          <div>
            <label className="rb-label">First name</label>
            <input className="rb-input" defaultValue="Julien" />
          </div>
          <div>
            <label className="rb-label">Nom</label>
            <input className="rb-input" defaultValue="Pernaud" />
          </div>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label className="rb-label">Role</label>
          <div style={{
            border: "1px solid var(--border-default)", borderRadius: 6,
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "0 10px", height: 32, fontSize: 13,
          }}>
            <span>Associate Lawyer</span>
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
          <span>5 seats remaining on your Cabinet plan (12 seats).</span>
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

Object.assign(window, { SettingsScreen, InviteMBdal });
