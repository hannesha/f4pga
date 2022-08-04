#!/usr/bin/env bash
#
# Copyright (C) 2020-2022 F4PGA Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

set -e

source $(dirname "$0")/env
source $(dirname "$0")/vpr_common.f4pga.sh
parse_args $@

DESIGN=${EBLIF/.eblif/}

[ ! -z "${JSON}" ] && JSON_ARGS="--json-constraints ${JSON}" || JSON_ARGS=
[ ! -z "${PCF_PATH}" ] && PCF_ARGS="--pcf-constraints ${PCF_PATH}" || PCF_ARGS=

export PYTHONPATH=$F4PGA_SHARE_DIR/scripts:$PYTHONPATH

`which python3` "$F4PGA_SHARE_DIR"/scripts/repacker/repack.py \
  --vpr-arch ${ARCH_DEF} \
  --repacking-rules ${ARCH_DIR}/${DEVICE_1}.repacking_rules.json \
  $JSON_ARGS \
  $PCF_ARGS \
  --eblif-in ${DESIGN}.eblif \
  --net-in ${DESIGN}.net \
  --place-in ${DESIGN}.place \
  --eblif-out ${DESIGN}.repacked.eblif \
  --net-out ${DESIGN}.repacked.net \
  --place-out ${DESIGN}.repacked.place \
  --absorb_buffer_luts on \
  >repack.log 2>&1