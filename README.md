# <p align="center">🦖 OP Shop Discord Bot</p>
<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/Discord.py-2.0+-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="Discord.py">
  <img src="https://img.shields.io/badge/MongoDB-Powered-47A248?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB">
  <img src="https://img.shields.io/badge/Architecture-Modular-FFD700?style=for-the-badge" alt="Architecture">
</p>

---

## 💎 The Enterprise Layer for ARK PvP Communities

**OP Shop** is not just another Discord bot—it is a **Discord-native SaaS platform** designed for high-stakes ARK: Survival Ascended / Evolved PvP marketplaces. Built with a data-driven philosophy, it provides a complete commerce, reputation, and community trust layer for Small Tribes and Crossplay PvP communities.

> [!IMPORTANT]
> **Zero Hardcoding Policy**: Every category, item, price, and reward flow is 100% dynamic and controllable via the in-Discord Admin Panel.

---

## 🚀 Core Features

### 🛒 Dynamic Shop Engine
*   **Fully Configurable**: Create, rename, and reorder categories and items on the fly.
*   **Item Metadata**: Custom questions, base prices, and conditional ticket requirements.
*   **Step-by-Step Flow**: Integrated purchase tickets that guide users through custom requirements (e.g., Tribe Name, Map, Delivery preferences).

### 🛡️ Trust & Reputation System
*   **Anti-Scam Layer**: Sophisticated XP and Trust metrics to identify and reward loyal members.
*   **Reputation Gating**: Automatically gate recruiting and LFT channels based on verifiable trust scores.
*   **XP Multipliers**: Reward long-term members with accelerated leveling and perks.

### 💰 Integrated Economy
*   **Dual-Currency System**: 
    *   **Credits**: For high-value marketplace transactions.
    *   **Tokens**: Earned through activity and purchases, spent on chat effects and fun redeems.
*   **Automated Rewards**: XP and Tokens are automatically distributed upon successful transaction completion.

### 🎫 Advanced Ticket Management
*   **Modular Flows**: Different ticket types for Shop Orders, Support, and General Inquiries.
*   **Transcripts**: Automatic archival of all interactions for audit and security.
*   **Staff Dashboards**: Streamlined UI for staff to manage orders without leaving Discord.

### 🤖 ARK-Themed AI Assistant
*   **Context Aware**: Answers FAQs about the shop, items, and community rules.
*   **Onboarding**: Guides new users through the marketplace ecosystem with an ARK-themed personality.

---

## 🛠️ Technology Stack

| Component | Technology |
| :--- | :--- |
| **Language** | Python 3.11+ |
| **Framework** | Discord.py (Async-first) |
| **Database** | MongoDB (Single source of truth) |
| **Deployment** | Docker & Jenkins (CI/CD Ready) |
| **Architecture** | Modular Service-Oriented Design |

---

## 📂 Project Structure

```text
core/               # Bot foundation (Config, Permissions, Logging)
modules/
  ├─ shop/          # Data-driven commerce engine
  ├─ tickets/       # Modular ticket & purchase flows
  ├─ economy/       # Credits, Tokens, and Reward logic
  ├─ profile/       # User XP, Trust scores, and Stats
  ├─ admin/         # In-Discord Management Panel
  ├─ ai/            # Contextual AI Assistant
  └─ ...             # Audits, Moderation, Sticky Messages
utils/              # Shared helpers and DB wrappers
```

---

## ⚙️ Quick Start

### 1. Prerequisites
*   Python 3.11+
*   MongoDB Instance
*   Discord Bot Token (Developer Portal)

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/your-repo/op-shop-bot.git

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials
```

### 3. Launch
```bash
python main.py
```

---

## 🛡️ Administrative Control
Forget about editing JSON files or restarting the bot. Use the `/shop-admin` command to:
- ✨ **Create** categories and items.
- 💸 **Adjust** prices and reward rates.
- 📊 **Monitor** transaction logs and trust metrics.
- ⚙️ **Configure** server-specific rules.

---

<p align="center">
  Built for the <b>ARK PvP Community</b> with ❤️ by the OP Shop Team.
</p>
