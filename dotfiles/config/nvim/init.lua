vim.g.ale_lint_on_text_changed = 'never'
vim.g.ale_lint_on_insert_leave = 0
vim.g.ale_lint_on_enter = 0
vim.g.ale_lint_on_save = 1
vim.g.ale_linters_ignore = { python = { 'mypy', 'pylint', 'pyright' } }

vim.g.netrw_liststyle = 1
vim.g.is_posix = 1

vim.pack.add({
  'https://github.com/dense-analysis/ale',
  'https://github.com/Vimjas/vim-python-pep8-indent',
  'https://github.com/jremmen/vim-ripgrep',
})
vim.opt.runtimepath:append('/opt/homebrew/opt/fzf')

vim.opt.listchars = { tab = '»·', trail = '·' }
vim.opt.list = true

vim.keymap.set('n', '<CR>', ':noh<CR><CR>')
vim.keymap.set('n', '<D-F>', ':FZF<CR>')

local function random_colorscheme()
  local names = vim.fn.getcompletion('', 'color')
  vim.cmd.colorscheme(names[os.time() % #names + 1])
end

local function is_in_worktrees(dir)
  return dir:find('/worktrees/', 1, true) ~= nil or vim.endswith(dir, '/worktrees')
end

local function apply_colorscheme_for(dir)
  if is_in_worktrees(dir) then
    vim.cmd.colorscheme('morning')
  elseif vim.fs.relpath(vim.fn.expand('~/src'), dir) then
    random_colorscheme()
  else
    vim.cmd.colorscheme('peachpuff')
  end
end

local function copy()
  vim.cmd([[normal! "+y]])
end

local function paste()
  vim.api.nvim_paste(vim.fn.getreg('+'), true, -1)
end

local function set_macos_clipboard_keys()
  vim.keymap.set('v', '<D-c>', copy, { silent = true, desc = 'Copy' })
  vim.keymap.set({ 'n', 'i', 'v', 'c', 't' }, '<D-v>', paste, { silent = true, desc = 'Paste' })
end

if vim.g.neovide then
  vim.o.guifont = 'Andale Mono:h18'

  vim.g.neovide_cursor_animation_length = 0
  vim.g.neovide_cursor_trail_size = 0
  vim.g.neovide_scroll_animation_length = 0

  apply_colorscheme_for(vim.fn.getcwd())
  vim.api.nvim_create_user_command('NewColor', random_colorscheme, {})
  set_macos_clipboard_keys()
end
