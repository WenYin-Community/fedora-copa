# bash completion for copa
_copa() {
    local cur prev commands
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    commands="search install info list repo repoquery provides doctor audit"

    if [[ ${cur} == -* ]] ; then
        COMPREPLY=( $(compgen -W "--help --version --json" -- ${cur}) )
        return 0
    fi

    case ${prev} in
        search)
            COMPREPLY=( $(compgen -W "--official-only --rpmfusion-only --copr-only --obs-only --no-obs --include-local-repo --json" -- ${cur}) )
            return 0
            ;;
        install)
            COMPREPLY=( $(compgen -W "--official-only --rpmfusion-only --copr-only --copr --obs-only --include-local-repo --no-obs --allow-obs-fallback --keep-copr --dry-run -y --assumeyes --json" -- ${cur}) )
            return 0
            ;;
        repo)
            COMPREPLY=( $(compgen -W "list enable disable remove" -- ${cur}) )
            return 0
            ;;
        repoquery)
            COMPREPLY=( $(compgen -W "--requires --provides --files" -- ${cur}) )
            return 0
            ;;
        list)
            COMPREPLY=( $(compgen -W "--packages --json" -- ${cur}) )
            return 0
            ;;
        info)
            COMPREPLY=( $(compgen -W "--json" -- ${cur}) )
            return 0
            ;;
        copr|obs)
            case ${COMP_WORDS[COMP_CWORD-2]} in
                repo)
                    COMPREPLY=( $(compgen -W "enable disable remove" -- ${cur}) )
                    return 0
                    ;;
            esac
            ;;
    esac

    COMPREPLY=( $(compgen -W "${commands}" -- ${cur}) )
    return 0
}
complete -F _copa copa
