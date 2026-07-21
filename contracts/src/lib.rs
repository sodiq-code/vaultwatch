#![cfg_attr(not(test), no_std)]
#![cfg_attr(not(test), no_main)]

pub mod audit_trail;
pub mod risk_oracle;
pub mod sentinel_credit;
pub mod sentinel_registry;
pub mod sentinel_alert_log;
pub mod agent_behavior_index;
pub mod risk_policy_manager;
pub mod risk_policy_manager_v2;
pub mod subscriber_vault;

// Custom memory operations to avoid WASM bulk-memory proposal
// Required for Casper testnet compatibility (no bulk-memory support)
#[cfg(all(target_arch = "wasm32", not(test)))]
mod memops {
    #[no_mangle]
    pub unsafe extern "C" fn memcpy(dest: *mut u8, src: *const u8, n: usize) -> *mut u8 {
        let mut i = 0;
        while i < n {
            *dest.add(i) = *src.add(i);
            i += 1;
        }
        dest
    }

    #[no_mangle]
    pub unsafe extern "C" fn memmove(dest: *mut u8, src: *const u8, n: usize) -> *mut u8 {
        if dest as usize <= src as usize || dest as usize >= src as usize + n {
            memcpy(dest, src, n)
        } else {
            let mut i = n;
            while i > 0 {
                i -= 1;
                *dest.add(i) = *src.add(i);
            }
            dest
        }
    }

    #[no_mangle]
    pub unsafe extern "C" fn memset(dest: *mut u8, c: i32, n: usize) -> *mut u8 {
        let mut i = 0;
        while i < n {
            *dest.add(i) = c as u8;
            i += 1;
        }
        dest
    }

    #[no_mangle]
    pub unsafe extern "C" fn memcmp(s1: *const u8, s2: *const u8, n: usize) -> i32 {
        let mut i = 0;
        while i < n {
            let a = *s1.add(i);
            let b = *s2.add(i);
            if a != b {
                return a as i32 - b as i32;
            }
            i += 1;
        }
        0
    }

    #[no_mangle]
    pub unsafe extern "C" fn bcmp(s1: *const u8, s2: *const u8, n: usize) -> i32 {
        memcmp(s1, s2, n)
    }
}
