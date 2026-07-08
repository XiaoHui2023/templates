#!/usr/bin/env bash
# 将当前目录下的源目录拷贝到目标根目录，目录名追加 -HHMM 时间后缀。
# 用软链接记录最近一次拷贝路径；若该路径仍存在，则删除上上次拷贝的目录。

set -euo pipefail

# ---------- 可配置变量 ----------
SOURCE_NAME="my_dir"              # 当前目录下要拷贝的目录名
DEST_ROOT="/path/to/destination"  # 拷贝目标根目录
LINK_NAME=".last_copy"            # 记录最近一次拷贝路径的软链接名
PREV_FILE=".prev_copy"            # 记录上上次拷贝路径的文本文件

# ---------- 路径解析 ----------
WORKDIR="$(pwd)"

SOURCE_PATH="${WORKDIR}/${SOURCE_NAME}"
if [[ ! -e "${SOURCE_PATH}" ]]; then
  echo "错误: 源路径不存在: ${SOURCE_PATH}" >&2
  exit 1
fi

TIMESTAMP="$(date +%H%M)"
BASE_NAME="$(basename "${SOURCE_PATH}")"
DEST_DIR="${DEST_ROOT}/${BASE_NAME}-${TIMESTAMP}"

mkdir -p "${DEST_ROOT}"

# ---------- 拷贝前：若上次拷贝仍在，则删除上上次目录 ----------
OLD_LAST=""
if [[ -L "${WORKDIR}/${LINK_NAME}" ]]; then
  OLD_LAST="$(readlink "${WORKDIR}/${LINK_NAME}")"
  if [[ -n "${OLD_LAST}" && -e "${OLD_LAST}" ]]; then
    if [[ -f "${WORKDIR}/${PREV_FILE}" ]]; then
      OLD_PREV="$(<"${WORKDIR}/${PREV_FILE}")"
      if [[ -n "${OLD_PREV}" && -e "${OLD_PREV}" ]]; then
        echo "删除上上次拷贝目录: ${OLD_PREV}"
        rm -rf "${OLD_PREV}"
      fi
    fi
  fi
fi

# ---------- 执行拷贝 ----------
echo "拷贝 ${SOURCE_PATH} -> ${DEST_DIR}"
cp -a "${SOURCE_PATH}" "${DEST_DIR}"

DEST_ABS="$(cd "${DEST_DIR}" && pwd)"

# ---------- 更新状态：prev 记旧 last，软链接指向新目录 ----------
if [[ -n "${OLD_LAST}" ]]; then
  printf '%s\n' "${OLD_LAST}" > "${WORKDIR}/${PREV_FILE}"
fi
ln -sfn "${DEST_ABS}" "${WORKDIR}/${LINK_NAME}"

echo "完成。软链接 ${WORKDIR}/${LINK_NAME} -> ${DEST_ABS}"
