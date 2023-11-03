" vimrc, R.Wobst, 6.12.2003

set nocompatible
set autoindent
set visualbell
set shiftwidth=4
"set showmode
set showmatch
"set showcmd
set ruler
set nojoinspaces
set cpo+=$
set whichwrap=""
set modelines=0
"colorscheme evening
"set number

if has('unix')
    let s:uname = system('uname')
    if s:uname == "Linux\n"
      " set term=linux
      " set term=xterm-256color
      " let &t_Co=256
    elseif s:uname == "SunOS\n"
      set term=dtterm
    elseif s:uname == "AIX\n"
      set term=dtterm
    else
      set term=xterm
    endif
endif

syntax enable
" Uncomment the following to have Vim jump to the last position when
" reopening a file
if has("autocmd")
  au BufReadPost * if line("'\"") > 1 && line("'\"") <= line("$") | exe "normal! g'\"" | endif
endif

" Uncomment the following to have Vim load indentation rules and plugins
" according to the detected filetype.
if has("autocmd")
  filetype plugin indent on
endif

hi DiffAdd ctermfg=Gray

" activate folding
" zi ... toggle all folds
" zo ... open
" zc ... close
let python_highlight_all = 1
let python_fold = 1
let java_fold = 1
let perl_fold = 1
let sh_fold_enabled = 1
let php_folding = 1
let c_no_comment_fold = 1

set makeprg=gcc\ -o\ %<\ %

"
" The following function and maps allow for [[ and ]] to search for a
" single char under the cursor.
"
function Cchar()
        let c = getline(line("."))[col(".") - 1]
        let @/ = c
endfunction
map [[ :call Cchar()<CR>n
map ]] :call Cchar()<CR>N
"
" Use F4 to switch between hex and ASCII editing
"
function Fxxd()
        let c=getline(".")
        if c =~ '^[0-9a-f]\{7}:'
                :%!xxd -r
        else
                :%!xxd -g4
        endif
endfunction

" key mappings
" F1  ... help
" F2  ... write file
" F3  ... quit vi
" F4  ... toggle hex mode
" F5  ... gqap ... format paragraph
" F8  ... write to pipe ~/p
" F9  ... read from pipe ~/p
" F10 ... quit and force writing
"
cmap <F1> :help
map <F2> :w<CR>
imap <F2> w<CR>a

map <F3> :q<CR>
imap <F3> q<CR>

map <F4> :call Fxxd()<CR>

map <F5> gqap

cmap <F8> w ! cat - >~/p<CR>

nmap <F9> :r ~/p<CR>

map <F10> :wq!<CR>
imap <F10> wq!<CR>

nmap <F11> <C-]>

" folding c/cpp/java
map <silent> <F12> :FOLD<CR>


" open all folds
normal zi

" disable mouse (want to have clipboard)
set mouse=

" http://vim.wikia.com/wiki/Super_retab
command! -nargs=1 -range SuperRetab <line1>,<line2>s/\v%(^ *)@<= {<args>}/\t/g

if &diff
    let &t_Co=256
    colorscheme murphy
    "colorscheme slate
    " highlight DiffAdd    cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
    " highlight DiffDelete cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
    " highlight DiffChange cterm=bold ctermfg=10 ctermbg=17 gui=none guifg=bg guibg=Red
    " highlight DiffText   cterm=bold ctermfg=10 ctermbg=88 gui=none guifg=bg guibg=Red
endif

" ~/.vimrc ends here
