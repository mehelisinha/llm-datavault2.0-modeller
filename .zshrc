
# ~/.zshrc

# --------------------------------------------------
# Homebrew (Apple Silicon Mac)
# --------------------------------------------------
eval "$(/opt/homebrew/bin/brew shellenv)"

# --------------------------------------------------
# PATH additions
# --------------------------------------------------
export PATH="$HOME/bin:$PATH"
export PATH="$HOME/.local/bin:$PATH"

# --------------------------------------------------
# Python / pyenv (optional - uncomment if used)
# --------------------------------------------------
# export PYENV_ROOT="$HOME/.pyenv"
# export PATH="$PYENV_ROOT/bin:$PATH"
# eval "$(pyenv init -)"

# --------------------------------------------------
# Aliases
# --------------------------------------------------
alias ll="ls -lah"
alias gs="git status"
alias gc="git commit"
alias gp="git push"

# --------------------------------------------------
# Prompt (optional)
# --------------------------------------------------
autoload -Uz colors && colors
PROMPT='%F{green}%n@%m%f %F{blue}%1~%f %# '

# --------------------------------------------------
# direnv (IMPORTANT)
# must be near bottom of file
# --------------------------------------------------
eval "$(direnv hook zsh)"

# --------------------------------------------------
# Optional: auto-load nvm / node
# --------------------------------------------------
# export NVM_DIR="$HOME/.nvm"
# [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && . "/opt/homebrew/opt/nvm/nvm.sh"

# --------------------------------------------------
# Optional: custom scripts
# --------------------------------------------------
# source "$HOME/.aliases"

# --------------------------------------------------
# End
# --------------------------------------------------
