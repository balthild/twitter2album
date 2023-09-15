package main

import (
	"encoding/json"
	"os"
	"sync"
)

type UserFlags struct {
	path  string
	cache map[int64]bool
	lock  sync.RWMutex
}

func LoadUserFlags(path string) (*UserFlags, error) {
	flags := make(map[int64]bool)

	data, err := os.ReadFile(path)
	if err != nil && !os.IsNotExist(err) {
		return nil, err
	}
	if err == nil {
		json.Unmarshal(data, &flags)
	}

	return &UserFlags{path, flags, sync.RWMutex{}}, nil
}

func (flags *UserFlags) setWithoutLock(id int64, val bool) {
	flags.cache[id] = val

	data, err := json.Marshal(flags.cache)
	if err == nil {
		os.WriteFile(flags.path, data, 0666)
	}
}

func (flags *UserFlags) Get(id int64) bool {
	flags.lock.RLock()
	flag := flags.cache[id]
	flags.lock.RUnlock()
	return flag
}

func (flags *UserFlags) Set(id int64, val bool) {
	flags.lock.Lock()
	flags.setWithoutLock(id, val)
	flags.lock.Unlock()
}

func (flags *UserFlags) Toggle(id int64) bool {
	flags.lock.Lock()
	new := !flags.cache[id]
	flags.setWithoutLock(id, new)
	flags.lock.Unlock()
	return new
}
