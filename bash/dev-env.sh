#!/usr/bin/env bash
# =============================================================================
# dev-env.sh — Genera el layout de Zellij dinámicamente y lanza el entorno
# Uso: dev-env.sh [mismas flags que dev-start.sh]
# =============================================================================

set -euo pipefail

# ── Colores ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV_START="$SCRIPT_DIR/dev-start"
LOG_DIR="$HOME/.local/share/dev-start/logs"
GENERATED_KDL="/tmp/dev-env-generated.kdl"

# ── Parámetros (mismos que dev-start.sh) ─────────────────────────────────────
EXCLUDE_REPOS=""
INCLUDE_REPOS=""
SKIP_PROXY=false
CLEAN_LOGS=false
RUN_INSTALL=false

show_help() {
    echo -e "${BOLD}${CYAN}Uso:${RESET} dev-env [opciones]"
    echo ""
    echo "Genera el layout de Zellij dinámicamente y levanta el entorno."
    echo ""
    echo "Opciones:"
    echo -e "  ${GREEN}--exclude, -x${RESET}      Repositorios a omitir (separados por coma)."
    echo "                     Ejemplo: --exclude carnet-front,asistencia-back"
    echo -e "  ${GREEN}--include, -n${RESET}      Solo iniciar los elementos indicados (separados por coma)."
    echo "                     Valores: proxy, asistencia-back, asistencia-front, carnet-back, carnet-front"
    echo "                     Ejemplo: --include proxy,carnet-back,carnet-front"
    echo -e "  ${GREEN}--no-proxy${RESET}         Salta el inicio de Cloud SQL Proxy."
    echo -e "  ${GREEN}--clean, -c${RESET}        Limpia los logs antiguos antes de iniciar."
    echo -e "  ${GREEN}--install, -i${RESET}      Ejecuta npm install en cada repositorio antes de iniciar."
    echo -e "  ${GREEN}--help, -h${RESET}         Muestra este menú de ayuda."
    echo ""
    exit 0
}

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --exclude|-x) EXCLUDE_REPOS="$2"; shift 2 ;;
        --include|-n) INCLUDE_REPOS="$2"; shift 2 ;;
        --no-proxy) SKIP_PROXY=true; shift ;;
        --clean|-c) CLEAN_LOGS=true; shift ;;
        --install|-i) RUN_INSTALL=true; shift ;;
        --help|-h) show_help ;;
        *) echo -e "${RED}[ERROR]${RESET} Parámetro desconocido: $1"; exit 1 ;;
    esac
done

if [[ -n "$INCLUDE_REPOS" && -n "$EXCLUDE_REPOS" ]]; then
    echo -e "${RED}[ERROR]${RESET} --include y --exclude son mutuamente excluyentes. Usa solo uno."
    exit 1
fi

# ── Helpers de decisión ───────────────────────────────────────────────────────
# Devuelve 0 (true) si el servicio dado debe mostrarse como pane
should_show() {
    local name="$1"

    # Si hay include list, solo mostrar los que están en ella
    if [[ -n "$INCLUDE_REPOS" ]]; then
        [[ ",$INCLUDE_REPOS," == *",$name,"* ]] && return 0 || return 1
    fi

    # Si hay exclude list, ocultar los que están en ella
    if [[ -n "$EXCLUDE_REPOS" ]]; then
        [[ ",$EXCLUDE_REPOS," == *",$name,"* ]] && return 1 || return 0
    fi

    return 0
}

show_proxy() {
    [[ "$SKIP_PROXY" == true ]] && return 1
    should_show "proxy"
}

# ── Construir los flags para dev-start.sh ────────────────────────────────────
build_flags() {
    local flags=""
    [[ -n "$EXCLUDE_REPOS" ]] && flags+=" --exclude $EXCLUDE_REPOS"
    [[ -n "$INCLUDE_REPOS" ]] && flags+=" --include $INCLUDE_REPOS"
    [[ "$SKIP_PROXY"   == true ]] && flags+=" --no-proxy"
    [[ "$CLEAN_LOGS"   == true ]] && flags+=" --clean"
    [[ "$RUN_INSTALL"  == true ]] && flags+=" --install"
    echo "$flags"
}

# ── Pane helper ───────────────────────────────────────────────────────────────
log_pane() {
    local name="$1"
    local logfile="$2"
    cat <<PANE
                pane {
                    name "$name"
                    command "bash"
                    args "-c" "mkdir -p \"$LOG_DIR\" && touch \"$LOG_DIR/$logfile\" && tail -F \"$LOG_DIR/$logfile\""
                }
PANE
}

# ── Generar el KDL ────────────────────────────────────────────────────────────
generate_kdl() {
    local flags
    flags="$(build_flags)"

    # Determinar qué panes de log se van a incluir
    local has_ab has_cb has_af has_cf has_px
    should_show "asistencia-back"  && has_ab=true  || has_ab=false
    should_show "carnet-back"      && has_cb=true  || has_cb=false
    should_show "asistencia-front" && has_af=true  || has_af=false
    should_show "carnet-front"     && has_cf=true  || has_cf=false
    show_proxy                     && has_px=true  || has_px=false

    # Si ningún servicio está activo, avisa
    local total=0
    for v in "$has_ab" "$has_cb" "$has_af" "$has_cf" "$has_px"; do
        [[ "$v" == true ]] && ((total++)) || true
    done
    if ((total == 0)); then
        echo -e "${RED}[ERROR]${RESET} Ningún servicio activo con las flags dadas. Nada que mostrar."
        exit 1
    fi

    # ── Abrir KDL ─────────────────────────────────────────────────────────────
    {
        cat <<'HEADER'
layout {
    pane split_direction="vertical" {

        // ── Panel de Control ─────────────────────────────────────────────────
        pane size="30%" {
            name "⚡ Control"
            command "bash"
HEADER

        # La línea de args incluye los flags calculados
        echo "            args \"-c\" \"trap '' HUP; bash \\\"$DEV_START\\\"$flags; echo ''; echo '--- Script finalizado. Presiona Ctrl+C para salir ---'; exec bash\""

        cat <<'LOGS_START'
        }

        // ── Paneles de Logs ──────────────────────────────────────────────────
        pane split_direction="horizontal" {
LOGS_START

        # ── Fila Backends ─────────────────────────────────────────────────────
        local has_backends=false
        ([[ "$has_ab" == true ]] || [[ "$has_cb" == true ]]) && has_backends=true || true

        if [[ "$has_backends" == true ]]; then
            echo "            // Fila: Backends"
            echo "            pane split_direction=\"vertical\" {"
            [[ "$has_ab" == true ]] && log_pane "📦 Asistencia Back" "asistencia-back.log"
            [[ "$has_cb" == true ]] && log_pane "📦 Carnet Back"     "carnet-back.log"
            echo "            }"
        fi

        # ── Fila Frontends ────────────────────────────────────────────────────
        local has_frontends=false
        ([[ "$has_af" == true ]] || [[ "$has_cf" == true ]]) && has_frontends=true || true

        if [[ "$has_frontends" == true ]]; then
            echo "            // Fila: Frontends"
            echo "            pane split_direction=\"vertical\" {"
            [[ "$has_af" == true ]] && log_pane "🎨 Asistencia Front" "asistencia-front.log"
            [[ "$has_cf" == true ]] && log_pane "🎨 Carnet Front"     "carnet-front.log"
            echo "            }"
        fi

        # ── Fila Proxy ────────────────────────────────────────────────────────
        if [[ "$has_px" == true ]]; then
            echo "            // Fila: Proxy"
            echo "            pane size=\"20%\" {"
            echo "                name \"🗄️  Cloud SQL Proxy\""
            echo "                command \"bash\""
            echo "                args \"-c\" \"mkdir -p \\\"$LOG_DIR\\\" && touch \\\"$LOG_DIR/cloud-sql-proxy.log\\\" && tail -F \\\"$LOG_DIR/cloud-sql-proxy.log\\\"\""
            echo "            }"
        fi

        cat <<'FOOTER'
        }
    }

    // Barra de estado
    pane size=1 borderless=true {
        plugin location="zellij:status-bar"
    }
}
FOOTER
    } > "$GENERATED_KDL"
}

# ── Main ──────────────────────────────────────────────────────────────────────
echo -e "${BOLD}${CYAN}Generando layout de Zellij...${RESET}"
generate_kdl
echo -e "${GREEN}[OK]${RESET} Layout generado en: $GENERATED_KDL"
echo ""

if ! command -v zellij &>/dev/null; then
    echo -e "${RED}[ERROR]${RESET} zellij no encontrado en el PATH."
    exit 1
fi

echo -e "${CYAN}[INFO]${RESET} Lanzando Zellij con el layout generado..."
exec zellij --layout "$GENERATED_KDL"
