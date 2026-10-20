#pragma once
void test_ufs(void);
extern uint64_t ufs_userdata_first, ufs_userdata_last;
uint32_t ufs_read(uint32_t lba, uint32_t count, void *buf);
