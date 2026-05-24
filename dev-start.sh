#!/usr/bin/env bash
# =============================================================================
# dev-start.sh — Entorno de desarrollo Cincinnatus
# Levanta: GCP Auth → Cloud SQL Proxy → Backends → Frontends
# =============================================================================

set -euo pipefail

# ── Colores ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

# ── Configuración ─────────────────────────────────────────────────────────────
PROXY_BIN="$HOME/cloud-sql-proxy"
PROXY_INSTANCE="cic-ptd-dev:us-east1:cic-ptd-dev"
PROXY_PORT=5432

REPOS_DIR="$HOME/Documents/Work/Cincinnatus/Repositories"

ASISTENCIA_BACK="$REPOS_DIR/ptd-asistencia-back"
ASISTENCIA_FRONT="$REPOS_DIR/ptd-asistencia-front"
CARNET_BACK="$REPOS_DIR/ptd-carnet-back"
CARNET_FRONT="$REPOS_DIR/ptd-carnet-front"

LOG_DIR="$HOME/.local/share/dev-start/logs"
mkdir -p "$LOG_DIR"

# PIDs de procesos en background
declare -a BG_PIDS=()

# ── Parámetros de entrada ──────────────────────────────────────────────────────
EXCLUDE_REPOS=""
SKIP_PROXY=false
CLEAN_LOGS=false
RUN_INSTALL=false

show_help() {
    echo -e "${BOLD}${CYAN}Uso:${RESET} dev-start [opciones]"
    echo ""
    echo "Opciones:"
    echo -e "  ${GREEN}--exclude, -x${RESET}      Repositorios a omitir (separados por coma)."
    echo "                     Ejemplo: --exclude carnet-front,asistencia-back"
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
        --no-proxy) SKIP_PROXY=true; shift ;;
        --clean|-c) CLEAN_LOGS=true; shift ;;
        --install|-i) RUN_INSTALL=true; shift ;;
        --help|-h) show_help ;;
        *) echo -e "${RED}[ERROR]${RESET} Parámetro desconocido: $1"; exit 1 ;;
    esac
done


# ── Helpers ───────────────────────────────────────────────────────────────────
log_info()    { echo -e "${CYAN}[INFO]${RESET}  $*"; }
log_ok()      { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error()   { echo -e "${RED}[ERROR]${RESET} $*"; }
log_section() { echo -e "\n${BOLD}${CYAN}══════════════════════════════════════${RESET}"; \
                echo -e "${BOLD}${CYAN}  $*${RESET}"; \
                echo -e "${BOLD}${CYAN}══════════════════════════════════════${RESET}\n"; }

check_port() {
    if lsof -i :"$1" >/dev/null; then
        log_error "El puerto $1 ya está en uso. Detén el proceso antes de continuar."
        exit 1
    fi
}

# ── Limpieza al salir ─────────────────────────────────────────────────────────
cleanup() {
    echo ""
    log_warn "Señal de cierre recibida. Deteniendo todos los servicios..."
    for pid in "${BG_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            log_info "Terminando PID $pid..."
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    # Dar tiempo para cierre graceful
    sleep 2
    for pid in "${BG_PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
    log_ok "Todos los servicios detenidos. ¡Hasta luego!"
    exit 0
}

# SIGINT / SIGTERM → cleanup normal
# EXIT se separa para no triggerear cleanup en salidas normales del script
# SIGHUP se ignora: zellij lo envía al presionar ESC y NO debe matar los servicios
trap cleanup SIGINT SIGTERM
trap '' SIGHUP

# ── Verifica dependencias ──────────────────────────────────────────────────────
check_deps() {
    log_section "Verificando dependencias"
    local missing=0

    for cmd in gcloud npm node; do
        if command -v "$cmd" &>/dev/null; then
            log_ok "$cmd encontrado: $(command -v $cmd)"
        else
            log_error "$cmd no encontrado. Instálalo antes de continuar."
            ((missing++))
        fi
    done

    if [[ ! -x "$PROXY_BIN" ]]; then
        log_error "cloud-sql-proxy no encontrado o no ejecutable en: $PROXY_BIN"
        ((missing++))
    else
        log_ok "cloud-sql-proxy encontrado: $PROXY_BIN"
    fi

    for dir in "$ASISTENCIA_BACK" "$ASISTENCIA_FRONT" "$CARNET_BACK" "$CARNET_FRONT"; do
        if [[ -d "$dir" ]]; then
            log_ok "Repositorio encontrado: $(basename $dir)"
        else
            log_warn "Repositorio no encontrado: $dir"
        fi
    done

    # Verificar archivos .env
    log_info "Verificando archivos .env..."
    local env_warn=0
    for dir in "$ASISTENCIA_BACK" "$ASISTENCIA_FRONT" "$CARNET_BACK" "$CARNET_FRONT"; do
        if [[ -d "$dir" ]]; then
            if [[ ! -f "$dir/.env" ]]; then
                log_warn "$(basename $dir): archivo .env NO encontrado. El servidor puede fallar al iniciar."
                ((env_warn++))
            else
                log_ok "$(basename $dir): .env encontrado."
            fi
        fi
    done
    if (( env_warn > 0 )); then
        log_warn "$env_warn repositorio(s) sin .env. Crea los archivos antes de continuar."
    fi

    if (( missing > 0 )); then
        log_error "Faltan $missing dependencia(s) crítica(s). Abortando."
        exit 1
    fi
}

# ── Paso 1: GCP Auth ──────────────────────────────────────────────────────────
gcp_auth() {
    log_section "Paso 1: Autenticación GCP"

    # Intenta generar un token silenciosamente.
    # Si funciona → credenciales vigentes. Si falla → pide login.
    if gcloud auth application-default print-access-token &>/dev/null; then
        log_ok "Credenciales de GCP vigentes. Saltando login."
    else
        log_warn "Credenciales expiradas o no encontradas. Abriendo navegador..."
        if gcloud auth application-default login; then
            log_ok "Autenticación GCP completada exitosamente."
        else
            log_error "Falló la autenticación GCP. Abortando."
            exit 1
        fi
    fi
}

# ── Paso 2: Cloud SQL Proxy ───────────────────────────────────────────────────
start_proxy() {
    if [[ "$SKIP_PROXY" == true ]]; then
        log_warn "Saltando Cloud SQL Proxy (--no-proxy)"
        return 0
    fi
    log_section "Paso 2: Cloud SQL Proxy"
    check_port "$PROXY_PORT"
    local log_file="$LOG_DIR/cloud-sql-proxy.log"

    log_info "Iniciando proxy → $PROXY_INSTANCE (puerto $PROXY_PORT)"
    log_info "Log: $log_file"

    "$PROXY_BIN" --port "$PROXY_PORT" "$PROXY_INSTANCE" \
        > "$log_file" 2>&1 &

    local pid=$!
    BG_PIDS+=("$pid")

    # Verificar que arrancó correctamente
    sleep 2
    if kill -0 "$pid" 2>/dev/null; then
        log_ok "Cloud SQL Proxy activo (PID: $pid)"
    else
        log_error "Cloud SQL Proxy falló al iniciar. Revisa: $log_file"
        cat "$log_file"
        exit 1
    fi
}

# ── Helper: levantar un servicio Node ─────────────────────────────────────────
# Uso: start_node_service <nombre> <directorio> [args...]
start_node_service() {
    local name="$1"
    local dir="$2"
    shift 2
    local extra_args=("$@")
    local log_file="$LOG_DIR/${name}.log"

    # Verificar si el repositorio fue excluido por el usuario
    if [[ ",$EXCLUDE_REPOS," == *",$name,"* ]]; then
        log_warn "[$name] Excluido por el usuario (--exclude). Saltando..."
        return 0
    fi

    if [[ ! -d "$dir" ]]; then
        log_warn "Directorio no encontrado, omitiendo: $dir"
        return 0
    fi


    log_info "[$name] Iniciando servidor de desarrollo..."
    # Truncar el log para que el watcher sólo vea output nuevo
    > "$log_file"
    (
        cd "$dir"
        if [[ "$RUN_INSTALL" == true ]]; then
            log_info "[$name] Instalando dependencias (npm install)..."
            npm install >> "$log_file" 2>&1
        fi
        if [[ ${#extra_args[@]} -gt 0 ]]; then
            exec npm run dev -- "${extra_args[@]}" >> "$log_file" 2>&1
        else
            exec npm run dev >> "$log_file" 2>&1
        fi
    ) &

    local pid=$!
    BG_PIDS+=("$pid")
    log_ok "[$name] Servidor iniciado (PID: $pid) | Log: $log_file"
}

# ── Paso 3: Backends ──────────────────────────────────────────────────────────
start_backends() {
    log_section "Paso 3: Backends"
    start_node_service "asistencia-back" "$ASISTENCIA_BACK"
    sleep 1
    start_node_service "carnet-back"     "$CARNET_BACK"
    sleep 1
}

# ── Esperar readiness de backends (fix race condition de auth) ────────────────
wait_for_backends() {
    local port="${1:-3000}"
    log_info "Esperando a que el backend levante en el puerto $port..."
    local retries=30
    while ! nc -z localhost "$port" 2>/dev/null; do
        ((retries--))
        if ((retries == 0)); then
            log_warn "Tiempo de espera agotado para el backend (puerto $port). Continuando de todos modos..."
            return 0
        fi
        sleep 1
    done
    log_ok "Backend listo en puerto $port."
}

# ── Paso 4: Frontends ─────────────────────────────────────────────────────────
start_frontends() {
    log_section "Paso 4: Frontends"
    # Forzar puertos para evitar colisiones. Vite usa el 5173 por defecto.
    # Carnet lo forzamos al 5173 porque Google OAuth lo tiene registrado así.
    # Asistencia lo movemos al 5174.
    start_node_service "asistencia-front" "$ASISTENCIA_FRONT" --port 5174 --strictPort
    sleep 1
    start_node_service "carnet-front"     "$CARNET_FRONT"     --port 5173 --strictPort
    sleep 1
}

# ── Panel de estado ───────────────────────────────────────────────────────────
show_status() {
    log_section "Entorno listo"
    echo -e "  ${GREEN}●${RESET} Cloud SQL Proxy  → localhost:${PROXY_PORT}"
    echo -e "  ${GREEN}●${RESET} Asistencia Back  → ver log: ${LOG_DIR}/asistencia-back.log"
    echo -e "  ${GREEN}●${RESET} Asistencia Front → ver log: ${LOG_DIR}/asistencia-front.log"
    echo -e "  ${GREEN}●${RESET} Carnet Back      → ver log: ${LOG_DIR}/carnet-back.log"
    echo -e "  ${GREEN}●${RESET} Carnet Front     → ver log: ${LOG_DIR}/carnet-front.log"
    echo ""
    echo -e "  ${YELLOW}Logs en:${RESET} $LOG_DIR"
    echo -e "  ${YELLOW}Presiona Ctrl+C para detener todos los servicios.${RESET}"
    echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
    clear
    echo -e "${BOLD}${CYAN}"
    echo "  ╔══════════════════════════════════════════╗"
    echo "  ║    Cincinnatus — Dev Environment Start   ║"
    echo "  ╚══════════════════════════════════════════╝"
    echo -e "${RESET}"

    if [[ "$CLEAN_LOGS" == true ]]; then
        log_info "Limpiando logs de ejecuciones anteriores (--clean)..."
        rm -f "$LOG_DIR"/*.log
    fi

    check_deps
    gcp_auth
    start_proxy
    start_backends
    wait_for_backends 3000
    start_frontends
    show_status

    # Mantener el script activo — cuando se ejecuta desde zellij,
    # el pane de control permanece vivo mientras haya servicios corriendo.
    log_info "Monitoreando procesos (Ctrl+C para detener todo)..."
    wait
}

main "$@"
