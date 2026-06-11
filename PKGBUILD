# Maintainer: Mike <mike@example.com>

pkgname=music-organise-git
_pkgname=music-organise
pkgver=0.1.0.r0.g0000000
pkgrel=1
pkgdesc='Organise MP3 and FLAC files by tags and keep XSPF playlists updated'
arch=('any')
url='https://github.com/mike-cr/music-organise'
license=('custom')
depends=(
  'python'
  'python-mutagen'
  'python-prompt_toolkit'
)
makedepends=(
  'git'
  'python-build'
  'python-installer'
  'python-wheel'
)
checkdepends=(
  'python-pytest'
)
provides=("$_pkgname")
conflicts=("$_pkgname")
source=("git+$url.git")
sha256sums=('SKIP')

pkgver() {
  cd "$srcdir/$_pkgname"
  local base_version
  base_version="$(sed -n "s/^version = \"\\(.*\\)\"/\\1/p" pyproject.toml)"
  printf '%s.r%s.g%s' "$base_version" "$(git rev-list --count HEAD)" "$(git rev-parse --short HEAD)"
}

build() {
  cd "$srcdir/$_pkgname"
  python -m build --wheel --no-isolation
}

check() {
  cd "$srcdir/$_pkgname"
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q
}

package() {
  cd "$srcdir/$_pkgname"
  python -m installer --destdir="$pkgdir" dist/*.whl
}
