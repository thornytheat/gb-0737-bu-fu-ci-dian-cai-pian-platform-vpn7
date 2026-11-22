MESSAGES = {
    "SAMPLE_UNKNOWN": "样例不存在", "RUN_UNKNOWN": "裁床批次不存在",
    "FILE_MISSING": "文件无法读取", "FILE_LIMIT": "文件超出采信上限", "ENCODING": "不支持的文件编码",
    "EMPTY_FILE": "文件没有内容", "BLANK_FILE": "文件只有空行", "HEADER_ONLY": "文件只有表头",
    "BAD_HEADER": "列名不符合定义", "CSV_SYNTAX": "记录引号或分隔异常", "BAD_COLUMNS": "记录列数不符",
    "MISSING": "必填字段缺失", "BAD_VALUE": "字段格式或范围错误", "BAD_UNIT": "长度单位不支持",
    "SUB_MM": "长度未对齐毫米刻度", "KEY_CONFLICT": "相同编号内容冲突", "DUPLICATE": "等值重复记录",
    "KEY_UNTRUSTED": "同编号含坏行", "ROLL_UNKNOWN": "疵点未关联可信布卷", "COORD_DESC": "疵点起止反向",
    "COORD_OUTSIDE": "疵点坐标超卷", "POINT_WIDTH": "点疵起止坐标不同", "ZERO_SPAN": "段疵长度为零",
    "ROLL_HELD": "卷内疵点待定位，整卷封存", "PLAN_LIMIT": "规划规模超限，请拆单",
    "NO_COMPATIBLE_ROLL": "布种或幅宽不匹配", "ROLLS_HELD": "匹配布卷均封存",
    "SEGMENT_TOO_SHORT": "无单段可容纳该裁片", "CAPACITY_USED": "可用段已由求解方案分配",
    "STALE_RUN": "样例、刀口或规则版本已变更", "REPLAY_DIFF": "重算方案与归档不同",
    "STORE_BUSY": "归档库暂忙", "FORM_INVALID": "参数无效，检查刀口值",
}


class FabricError(Exception):
    def __init__(self, code, status=422, *, file=None, line=None):
        self.code, self.status, self.file, self.line = code, status, file, line
        super().__init__(MESSAGES[code])

    def response(self):
        return {"code": self.code, "message": str(self), "file": self.file, "line": self.line}
